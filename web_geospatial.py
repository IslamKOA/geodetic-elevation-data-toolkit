"""Small, bounded hosted AOI/GeoTIFF backend reusing original geoid_engine.

No local path access, shell calls, external grid downloads or DEM network retrieval.
"""
import io
import json
import math
import re
import secrets
import tempfile
import threading
import time
import zipfile
from pathlib import Path
from flask import Blueprint, Response, jsonify, request
from werkzeug.utils import secure_filename

geo_api=Blueprint("geo_api",__name__)
GEO_LOCK=threading.BoundedSemaphore(1)
FILES={}
FILES_LOCK=threading.Lock()
TTL=180
MAX_AOI_PIXELS=150000
MAX_RASTER_PIXELS=500000
ALLOWED={"raf20","ellipsoid"}

def fail(message,code=400):
    return jsonify(ok=False,error=message),code

def param(name,default=""):
    v=request.form.get(name,default)
    if not isinstance(v,str) or len(v)>120:raise ValueError("Invalid field: "+name)
    return v.strip()

def save_upload(up,folder,extensions,limit=8*1024*1024):
    if not up or not up.filename:raise ValueError("Missing file.")
    name=secure_filename(Path(up.filename).name)
    if not name or Path(name).suffix.lower() not in extensions:raise ValueError("Unsupported input format.")
    dest=Path(folder)/name
    data=up.stream.read(limit+1)
    if len(data)>limit:raise ValueError("Uploaded file exceeds hosted limit.")
    dest.write_bytes(data)
    return dest

def aoi_file(folder):
    from werkzeug.datastructures import FileStorage
    parts=request.files.getlist("aoi_parts")
    if not parts and request.files.get("aoi"):parts=[request.files["aoi"]]
    if not parts or len(parts)>7:raise ValueError("Upload one AOI or a shapefile with its companion files.")
    allowed={".json",".geojson",".gpkg",".zip",".shp",".shx",".dbf",".prj",".cpg"}
    saved=[save_upload(p,folder,allowed) for p in parts if p.filename]
    candidates=[p for p in saved if p.suffix.lower() in {".json",".geojson",".gpkg",".zip",".shp"}]
    if len(candidates)!=1:raise ValueError("Choose exactly one AOI dataset.")
    main=candidates[0]
    if main.suffix.lower()==".zip":
        with zipfile.ZipFile(main) as archive:
            infos=archive.infolist()
            if len(infos)>12 or sum(i.file_size for i in infos)>8*1024*1024:
                raise ValueError("AOI archive exceeds hosted extraction limits.")
            extracted=[]
            for info in infos:
                name=Path(info.filename)
                if info.is_dir():continue
                if len(name.parts)!=1 or name.suffix.lower() not in allowed or info.flag_bits&1:
                    raise ValueError("ZIP must contain only flat, unencrypted shapefile components.")
                path=Path(folder)/secure_filename(name.name)
                if path.exists():raise ValueError("Duplicate archive member.")
                with archive.open(info) as source,open(path,"wb") as target:
                    data=source.read(8*1024*1024+1)
                    if len(data)>8*1024*1024:raise ValueError("Archive member too large.")
                    target.write(data)
                extracted.append(path)
            shp=[p for p in extracted if p.suffix.lower()==".shp"]
            if len(shp)!=1:raise ValueError("ZIP must contain exactly one shapefile.")
            main=shp[0]
    if main.suffix.lower()==".shp":
        if any(not main.with_suffix(ext).exists() for ext in (".shx",".dbf",".prj")):
            raise ValueError("Shapefile requires .shp, .shx, .dbf and .prj.")
    return main

def validate_aoi(path):
    import geopandas as gpd
    g=gpd.read_file(path)
    if g.empty or len(g)>50 or g.crs is None:raise ValueError("AOI needs a defined CRS and at most 50 features.")
    if not all(v in {"Polygon","MultiPolygon"} for v in g.geom_type):
        raise ValueError("AOI needs polygon geometry.")
    if any(p is None or p.is_empty or not p.is_valid for p in g.geometry):
        raise ValueError("AOI polygons must be valid and nonempty.")
    vertices=sum(len(p.exterior.coords)+sum(len(r.coords) for r in p.interiors) for geom in g.geometry for p in (geom.geoms if geom.geom_type=="MultiPolygon" else [geom]))
    if vertices>15000:raise ValueError("Too many AOI vertices.")
    return g

def output_crs(g,requested):
    from pyproj import CRS
    crs=CRS.from_user_input(requested) if requested else (CRS.from_user_input(g.crs) if g.crs.is_projected else CRS.from_user_input(g.estimate_utm_crs()))
    if not crs.is_projected or not crs.axis_info or crs.axis_info[0].unit_name.lower() not in {"metre","meter"}:
        raise ValueError("Output CRS must be projected in metres.")
    return crs.to_string()

def store_result(paths,metadata):
    out=io.BytesIO()
    with zipfile.ZipFile(out,"w",compression=zipfile.ZIP_DEFLATED) as z:
        for path in paths:z.write(path,Path(path).name)
        z.writestr("metadata.json",json.dumps(metadata,indent=2))
    if out.tell()>24*1024*1024:raise ValueError("Compressed result exceeds hosted limit.")
    token=secrets.token_urlsafe(24)
    now=time.time()
    with FILES_LOCK:
        for k,(t,_) in list(FILES.items()):
            if now-t>TTL:FILES.pop(k,None)
        if len(FILES)>8:FILES.pop(min(FILES,key=lambda x:FILES[x][0]),None)
        FILES[token]=(now,out.getvalue())
    return "/geo-download/"+token

@geo_api.post("/inspect")
def inspect():
    if request.content_length is None or request.content_length>10*1024*1024:
        return fail("AOI upload too large for hosted preview.",413)
    try:
        with tempfile.TemporaryDirectory(prefix="geoid_aoi_") as td:
            g=validate_aoi(aoi_file(td))
            return jsonify(ok=True,crs=g.crs.to_string())
    except Exception as e:return fail(str(e))

def run_geo():
    mode=param("mode")
    if mode not in {"aoi","raster"}:return fail("Unsupported workflow.",503)
    if request.content_length is None or request.content_length>12*1024*1024:
        return fail("Hosted upload maximum is 12 MB.",413)
    if not GEO_LOCK.acquire(blocking=False):
        return fail("Geospatial server is busy. Retry shortly.",503)
    try:
        model=param("model","raf20").lower()
        source=param("source","ellipsoid").lower()
        target=param("target","raf20").lower()
        if model!="raf20" or source not in ALLOWED or target not in ALLOWED:
            return fail("Hosted raster/AOI preview currently supports RAF20 and ellipsoidal heights only.",503)
        if request.files.get("custom") or param("raster_path"):
            return fail("Custom grid and server-local raster paths are not available online.",503)
        from geoid_engine import aoi_process,raster_process
        with tempfile.TemporaryDirectory(prefix="geoid_job_") as td:
            folder=Path(td)
            if mode=="aoi":
                aoi=aoi_file(folder)
                g=validate_aoi(aoi)
                crs=output_crs(g,param("crs"))
                resolution=float(param("resolution","30"))
                if not math.isfinite(resolution) or not 1<=resolution<=10000:
                    raise ValueError("Hosted pixel size must be 1–10,000 m.")
                projected=g.to_crs(crs)
                bounds=projected.total_bounds
                pixels=max(1,math.ceil((bounds[2]-bounds[0])/resolution))*max(1,math.ceil((bounds[3]-bounds[1])/resolution))
                if pixels>MAX_AOI_PIXELS:raise ValueError("AOI exceeds 150,000 pixels; increase the pixel size.")
                products=aoi_process(aoi,folder,crs,resolution,model,None)
                message="AOI separation raster generated using original geoid engine."
            else:
                raster=save_upload(request.files.get("raster"),folder,{".tif",".tiff"})
                import rasterio
                with rasterio.open(raster) as ds:
                    if ds.count!=1 or ds.crs is None or ds.width*ds.height>MAX_RASTER_PIXELS:
                        raise ValueError("GeoTIFF must have one band, defined CRS, and at most 500,000 pixels.")
                    if ds.driver!="GTiff":raise ValueError("Input must be a GeoTIFF.")
                products=raster_process(raster,folder,source,target,model,None)
                message="Elevation raster transformed using original geoid engine."
            metadata={"workflow":mode,"model_N":model,"source_vertical":source,"target_vertical":target,
                "caution":"RAF20 is regional and height datum assumptions require scientific validation.",
                "scientific_engine":"original geoid_engine.py and vertical_reference.py"}
            url=store_result(products,metadata)
            return jsonify(ok=True,message=message,download=url,files=[Path(p).name for p in products],previews=[])
    except Exception as e:
        return fail(str(e))
    finally:
        GEO_LOCK.release()

@geo_api.get("/geo-download/<token>")
def download(token):
    if not re.fullmatch(r"[A-Za-z0-9_-]{30,64}",token):return fail("Invalid download.",404)
    with FILES_LOCK: record=FILES.pop(token,None)
    if record is None or time.time()-record[0]>TTL:return fail("Download expired; run again.",404)
    return Response(record[1],mimetype="application/zip",headers={"Content-Disposition":"attachment; filename=geodetic_raster_results.zip","Cache-Control":"no-store"})
