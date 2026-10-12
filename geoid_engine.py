"""Geoid-only workflows, extending the original vertical_reference.py (v1.0.1)."""
from pathlib import Path
import csv
import json
import numpy as np
import rasterio
from rasterio.transform import from_bounds
from rasterio.features import rasterize
from pyproj import Transformer, CRS, datadir, network
from pyproj.transformer import TransformerGroup
from pyproj.aoi import AreaOfInterest
from scipy.interpolate import RegularGridInterpolator
from vertical_reference import load_raf20, build_n_raster, convert_between_models

HERE=Path(__file__).resolve().parent
RAF=HERE/'data'/'RAF20.tac'
MODELS=('ellipsoid','raf20','egm96','egm2008','custom')
COMPOUND={'egm96':'EPSG:4326+5773','egm2008':'EPSG:4326+3855'}

def points_n(xs,ys,crs,model,custom=None,cache=None):
    xs=np.asarray(xs,dtype=float); ys=np.asarray(ys,dtype=float)
    if xs.shape!=ys.shape: raise ValueError('Coordinate columns have different lengths')
    if not np.all(np.isfinite(xs)&np.isfinite(ys)): raise ValueError('Non-finite input coordinates')
    if model=='ellipsoid': return np.zeros(len(xs))
    if model=='raf20':
        lon,lat=Transformer.from_crs(crs,'EPSG:4171',always_xy=True).transform(xs,ys)
        result=load_raf20(RAF)['interpolator'](np.column_stack([lat,lon]))
    elif model in COMPOUND:
        lon,lat=Transformer.from_crs(crs,'EPSG:4326',always_xy=True).transform(xs,ys)
        if not np.all(np.isfinite(lon)&np.isfinite(lat)): raise ValueError('Failed to transform coordinates')
        cache=Path(cache or HERE/'grid_cache');cache.mkdir(exist_ok=True,parents=True)
        datadir.append_data_dir(str(cache))
        aoi=AreaOfInterest(float(min(lon))-0.01,float(min(lat))-0.01,float(max(lon))+0.01,float(max(lat))+0.01)
        def group(): return TransformerGroup(COMPOUND[model], 'EPSG:4979', always_xy=True, area_of_interest=aoi, allow_ballpark=False)
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter('ignore'); g=group()
        if not g.best_available or not g.transformers:
            network.set_network_enabled(True)
            g.download_grids(directory=str(cache),open_license=True,verbose=False)
            datadir.append_data_dir(str(cache))
            with warnings.catch_warnings():
                warnings.simplefilter('ignore');g=group()
        if not g.best_available or not g.transformers: raise RuntimeError('Required EGM vertical grid is unavailable; connect to the internet or install the PROJ grid.')
        _,_,result=g.transformers[0].transform(lon,lat,np.zeros(len(xs)))
    elif model=='custom':
        if not custom: raise ValueError('Custom separation grid is required')
        with rasterio.open(custom) as ds:
            if not ds.crs: raise ValueError('Custom grid CRS is missing')
            xx,yy=Transformer.from_crs(crs,ds.crs,always_xy=True).transform(xs,ys)
            result=np.array([float(a[0]) for a in ds.sample(zip(xx,yy),masked=True)],float)
            if ds.nodata is not None: result[np.isclose(result,ds.nodata,equal_nan=False)]=np.nan
    else: raise ValueError('Unknown model')
    result=np.asarray(result,float)
    if not np.all(np.isfinite(result)): raise ValueError('Some points fall outside model coverage, or grid data is missing')
    return result

def point_rows(rows,crs,model,source='ellipsoid',target='raf20',custom=None,cache=None):
    x=np.array([float(r['x']) for r in rows]);y=np.array([float(r['y']) for r in rows]);
    n=points_n(x,y,crs,model,custom,cache)
    ns=points_n(x,y,crs,source,custom,cache) if any(str(r.get('z','')).strip() for r in rows) else np.zeros(len(rows))
    nt=points_n(x,y,crs,target,custom,cache) if any(str(r.get('z','')).strip() for r in rows) else np.zeros(len(rows))
    out=[]
    for i,r in enumerate(rows):
        q=dict(r);q['N_m']=round(float(n[i]),5)
        if str(r.get('z','')).strip():
            q['z_converted_m']=round(float(r['z'])+ns[i]-nt[i],5)
        out.append(q)
    return out

def aoi_template(geojson_path,output,crs,resolution):
    import geopandas as gpd
    aoi=gpd.read_file(geojson_path)
    if aoi.empty or aoi.crs is None: raise ValueError('AOI must contain geometry with a defined CRS')
    aoi=aoi.to_crs(crs)
    geom=[g for g in aoi.geometry if g is not None and not g.is_empty]
    if not geom: raise ValueError('Empty AOI geometry')
    bounds=aoi.total_bounds
    xmin,ymin,xmax,ymax=map(float,bounds)
    width=max(1,int(np.ceil((xmax-xmin)/resolution))); height=max(1,int(np.ceil((ymax-ymin)/resolution)))
    if width*height>12_000_000:raise ValueError('AOI output exceeds 12 million pixels. Increase pixel size.')
    transform=from_bounds(xmin,ymin,xmin+width*resolution,ymax if height==1 else ymin+height*resolution,width,height)
    # Pixel-aligned grid, top-left at xmin,ymin+height*resolution
    mask=rasterize(((g,1) for g in geom),out_shape=(height,width),transform=transform,fill=0,dtype='uint8',all_touched=True)
    output=Path(output)
    with rasterio.open(output,'w',driver='GTiff',width=width,height=height,count=1,dtype='float32',crs=crs,transform=transform,nodata=np.nan,compress='deflate') as dst:
        dst.write(np.where(mask>0,0,np.nan).astype('float32'),1)
    return output

def raster_process(input_path,outdir,source,target,model,custom=None):
    outdir=Path(outdir);outdir.mkdir(parents=True,exist_ok=True)
    with rasterio.open(input_path) as src:
        if src.count!=1 or src.crs is None: raise ValueError('Raster must have one band and a defined CRS')
    cache=outdir/'grid_cache';paths={}
    for name,m in [('source',source),('target',target),('model',model)]:
        if m!='ellipsoid' and m not in paths:
            p=outdir/f'N_{m}.tif'
            build_n_raster(input_path,p,m,raf20_path=RAF,custom_n_raster=custom,grid_cache_dir=cache)
            paths[m]=p
    out=outdir/'height_converted.tif'
    convert_between_models(input_path,out,source,target,source_n_path=paths.get(source),target_n_path=paths.get(target))
    return [out]+list(paths.values())

def aoi_process(aoi,outdir,crs,resolution,model,custom=None):
    if model=='ellipsoid':raise ValueError('Select a geoid model for AOI extraction')
    outdir=Path(outdir);outdir.mkdir(parents=True,exist_ok=True)
    template=aoi_template(aoi,outdir/'_aoi_template.tif',crs,resolution)
    target=outdir/f'geoid_separation_N_{model}.tif'
    try:build_n_raster(template,target,model,raf20_path=RAF,custom_n_raster=custom,grid_cache_dir=outdir/'grid_cache')
    finally:template.unlink(missing_ok=True)
    return [target]
