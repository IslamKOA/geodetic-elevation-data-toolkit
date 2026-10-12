"""Local-only browser UI. Launch with python geoid_web.py."""
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from urllib.parse import urlparse
from pathlib import Path
from tempfile import TemporaryDirectory
import webbrowser,threading,json,shutil,csv,io,zipfile,uuid,traceback,os,sys,subprocess
from email.parser import BytesParser
from email.policy import default
from geoid_engine import point_rows,points_n,aoi_process,raster_process

ROOT=Path(__file__).resolve().parent
RESULTS=ROOT/'outputs'; RESULTS.mkdir(exist_ok=True)
HTML=(ROOT/'geoid_interface.html').read_bytes()

class Field:
 def __init__(self, data, filename=None):
  self.filename=filename
  self.data=data
  self.file=io.BytesIO(data)
class Form(dict):
 def getfirst(self,key,default=''):
  item=self.get(key)
  return item.data.decode('utf-8-sig') if item is not None else default

def parse_form(headers, stream, size):
 if not 0<size<=400*1024*1024:raise ValueError('Browser upload exceeds 400 MB. For large GeoTIFFs, use the Local raster path field: the server reads the file directly from your disk.')
 content_type=headers.get('Content-Type','')
 if not content_type.startswith('multipart/form-data;'):raise ValueError('Expected multipart form')
 raw=b'Content-Type: '+content_type.encode()+b'\r\nMIME-Version: 1.0\r\n\r\n'+stream.read(size)
 parsed=BytesParser(policy=default).parsebytes(raw)
 form=Form()
 for part in parsed.iter_parts():
  name=part.get_param('name',header='content-disposition')
  if not name:continue
  filename=part.get_filename()
  payload=part.get_payload(decode=True)
  item=Field(payload if payload is not None else b'',filename)
  if name=='aoi_parts':form.setdefault(name,[]).append(item)
  else:form[name]=item
 return form

def fstr(form,key,default=''):
 return str(form.getfirst(key,default)).strip()
def uploaded(form,key,destination):
 if key not in form:return None
 item=form[key]
 if not item.filename:return None
 name=Path(item.filename).name
 if Path(name).suffix.lower() not in ('.tif','.tiff','.geojson','.json','.gpkg','.zip','.csv','.shp','.shx','.dbf','.prj','.cpg'):raise ValueError('Unsupported upload type')
 dest=Path(destination)/name
 with dest.open('wb') as out:shutil.copyfileobj(item.file,out)
 return dest

def unpack_aoi(path,folder):
 if path.suffix.lower()!='.zip':return path
 with zipfile.ZipFile(path) as z:
  if any(p.startswith('/') or '..' in Path(p).parts for p in z.namelist()):raise ValueError('Unsafe ZIP path')
  z.extractall(folder)
 shp=list(Path(folder).rglob('*.shp'))
 if len(shp)!=1:raise ValueError('ZIP AOI must contain one shapefile and its associated files')
 return shp[0]

def prepare_aoi(form,folder):
 """Accept a single standard vector file or all shapefile components in one picker."""
 folder=Path(folder)
 parts=form.get('aoi_parts',[])
 if not isinstance(parts,list):parts=[parts]
 candidates=[]
 for item in parts:
  if not item.filename:continue
  name=Path(item.filename).name
  if Path(name).suffix.lower() not in ('.shp','.shx','.dbf','.prj','.cpg','.zip','.geojson','.json','.gpkg'):
   raise ValueError('Unsupported AOI file type: '+name)
  target=folder/name
  target.write_bytes(item.data)
  candidates.append(target)
 legacy=uploaded(form,'aoi',folder)
 if legacy is not None:candidates.append(legacy)
 if not candidates:raise ValueError('Choose a GeoJSON, GPKG, ZIP, or all .shp/.shx/.dbf/.prj files together.')
 vector=[f for f in candidates if f.suffix.lower() in ('.shp','.geojson','.json','.gpkg','.zip')]
 if len(vector)!=1:
  raise ValueError('Choose exactly one AOI dataset: one GeoJSON/GPKG/ZIP, or one .shp with its .shx/.dbf/.prj.')
 main=unpack_aoi(vector[0],folder)
 if main.suffix.lower()=='.shp':
  missing=[x for x in ('.shx','.dbf','.prj') if not main.with_suffix(x).exists()]
  if missing:raise ValueError('Shapefile missing companion files: '+', '.join(missing)+'. Select all four in one file picker or upload a ZIP.')
 return main

def output_crs_for_aoi(path,requested):
 import geopandas as gpd
 from pyproj import CRS
 if requested:
  result=CRS.from_user_input(requested)
  if result.is_geographic:raise ValueError('The output CRS must be projected for metre-based output pixel sizes. Choose an EPSG UTM code or leave output CRS on Auto.')
  return result.to_string()
 gdf=gpd.read_file(path,rows=1)
 if gdf.crs is None:raise ValueError('Input AOI has no CRS. Provide its .prj or assign the CRS in GIS software.')
 crs=CRS.from_user_input(gdf.crs)
 if crs.is_projected and (crs.axis_info and crs.axis_info[0].unit_name.lower() in ('metre','meter')):return crs.to_string()
 utm=gdf.estimate_utm_crs()
 if utm is None:raise ValueError('Could not select an automatic projected CRS. Supply an output EPSG code.')
 return utm.to_string()

def aoi_crs(path):
 import geopandas as gpd
 data=gpd.read_file(path,rows=1)
 if data.crs is None:raise ValueError('AOI has no defined CRS. Supply a .prj file or define its CRS in GIS software.')
 return data.crs.to_string()

def create_previews(outputs, output_dir):
 """Create compact PNG raster previews with coordinate axes, grid, and contours."""
 try:
  import rasterio
  from rasterio.enums import Resampling
  import numpy as np
  import matplotlib
  matplotlib.use('Agg')
  import matplotlib.pyplot as plt
  from matplotlib.ticker import ScalarFormatter, MaxNLocator, FormatStrFormatter
 except ImportError as err:
  print('Preview unavailable:',err,flush=True)
  return []
 previews=[]
 for idx, src_path in enumerate(outputs):
  src_path=Path(src_path)
  if src_path.suffix.lower() not in ('.tif','.tiff'):continue
  try:
   with rasterio.open(src_path) as ds:
    factor=min(1.,850/max(ds.width,ds.height))
    shape=(max(1,int(ds.height*factor)),max(1,int(ds.width*factor)))
    values=ds.read(1,out_shape=shape,masked=True,resampling=Resampling.bilinear).astype('float64')
    data=np.ma.masked_invalid(values)
    if not data.count():continue
    lo,hi=np.percentile(data.compressed(),[2,98])
    if hi<=lo:lo,hi=float(data.min()),float(data.max())
    if hi<=lo:hi=lo+1
    bounds=ds.bounds
    extent=[bounds.left,bounds.right,bounds.bottom,bounds.top]
    fig,ax=plt.subplots(figsize=(10.5,7.2),dpi=115)
    color='terrain' if 'height' in src_path.name.lower() or 'dem' in src_path.name.lower() else 'viridis'
    im=ax.imshow(data,cmap=color,vmin=lo,vmax=hi,interpolation='nearest',extent=extent,origin='upper')
    ax.set_title(src_path.name+'  |  '+(f'EPSG:{ds.crs.to_epsg()}' if ds.crs and ds.crs.to_epsg() else 'Raster preview'),fontsize=10)
    crs_text=(f"EPSG:{ds.crs.to_epsg()}" if ds.crs and ds.crs.to_epsg() else (ds.crs.to_string() if ds.crs else "Unknown CRS"))
    is_geo=bool(getattr(ds.crs,'is_geographic',False)) if ds.crs else False
    xlab='Longitude' if is_geo else 'X coordinate'
    ylab='Latitude' if is_geo else 'Y coordinate'
    ax.set_xlabel(f"{xlab} ({'degrees' if is_geo else 'm'})",fontsize=9)
    ax.set_ylabel(f"{ylab} ({'degrees' if is_geo else 'm'})",fontsize=9)
    ax.grid(True,color='#ffffff',linewidth=.6,alpha=.55)
    ax.xaxis.set_major_locator(MaxNLocator(nbins=6))
    ax.yaxis.set_major_locator(MaxNLocator(nbins=6))
    if is_geo:
     ax.xaxis.set_major_formatter(FormatStrFormatter('%.4f'))
     ax.yaxis.set_major_formatter(FormatStrFormatter('%.4f'))
    else:
     fmt=ScalarFormatter(useOffset=False)
     fmt.set_scientific(False)
     ax.xaxis.set_major_formatter(fmt)
     ax.yaxis.set_major_formatter(fmt)
    finite=np.ma.filled(data,np.nan)
    rng=float(np.nanmax(finite)-np.nanmin(finite))
    if np.isfinite(rng) and rng>0:
     import numpy as _np
     rows,cols=finite.shape
     xs=_np.linspace(bounds.left,bounds.right,cols)
     ys=_np.linspace(bounds.top,bounds.bottom,rows)
     nlevels=8 if rng>0 else 0
     try:
      levels=_np.linspace(_np.nanpercentile(finite,8),_np.nanpercentile(finite,92),nlevels)
      levels=_np.unique(levels[_np.isfinite(levels)])
      if len(levels)>=3:
       cs=ax.contour(xs,ys,finite,levels=levels,colors='black',linewidths=.45,alpha=.55)
       ax.clabel(cs,inline=True,fontsize=7,fmt='%.2f')
     except Exception as contour_err:
      print('Contour preview warning for',src_path.name,contour_err,flush=True)
    cbar=fig.colorbar(im,ax=ax,label='Metres',shrink=.86)
    cbar.ax.tick_params(labelsize=8)
    name=f'preview_{idx}.png';path=output_dir/name
    fig.tight_layout()
    fig.savefig(path,bbox_inches='tight',facecolor='white');plt.close(fig)
    previews.append({'file':src_path.name,'url':'/preview/'+output_dir.name+'/'+name,'min':round(float(data.min()),3),'max':round(float(data.max()),3),'crs':crs_text,'width':ds.width,'height':ds.height})
  except Exception as err:
   print('Preview failed for',src_path.name,err,flush=True)
 return previews

class Handler(BaseHTTPRequestHandler):
 def reply(self,data,status=200,mime='application/json'):
  if isinstance(data,(dict,list)):data=json.dumps(data).encode()
  self.send_response(status);self.send_header('Content-Type',mime);self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
 def do_GET(self):
  p=urlparse(self.path).path
  if p=='/':return self.reply(HTML,mime='text/html; charset=utf-8')
  if p=='/health':return self.reply({'ok':True,'service':'geoid-server'})
  if p.startswith('/preview/'):
   parts=p.strip('/').split('/')
   if len(parts)!=3 or len(parts[1])!=32 or any(c not in '0123456789abcdef' for c in parts[1]) or not parts[2].startswith('preview_') or not parts[2].endswith('.png') or not parts[2][8:-4].isdigit():return self.reply({'error':'Invalid preview'},400)
   path=RESULTS/parts[1]/parts[2]
   if not path.is_file():return self.reply({'error':'Preview unavailable'},404)
   return self.reply(path.read_bytes(),mime='image/png')
  if p.startswith('/assets/'):
   name=p.split('/')[-1]
   if name not in ('uga.png','inrae.png','najah.png','institute.png'):return self.reply({'error':'Not found'},404)
   return self.reply((ROOT/'assets'/name).read_bytes(),mime='image/png')
  if p.startswith('/download/'):
   name=p.split('/')[-1]
   if not name.endswith('.zip') or '/' in name or '\\' in name:return self.reply({'error':'Invalid download'},400)
   path=RESULTS/name
   if not path.is_file():return self.reply({'error':'Missing output'},404)
   return self.reply(path.read_bytes(),mime='application/zip')
  self.reply({'error':'Not found'},404)
 def do_POST(self):
  if self.path not in ('/run','/dem','/inspect'):return self.reply({'error':'Not found'},404)
  try:
   limit=400*1024*1024
   size=int(self.headers.get('Content-Length','0'))
   if size>limit:raise ValueError('Browser upload exceeds 400 MB. Use the Local raster path field on the Elevation raster tab instead of uploading the file.')
   form=parse_form(self.headers,self.rfile,size)
   if self.path=='/inspect':
    with TemporaryDirectory() as td:
     aoi=prepare_aoi(form,td)
     return self.reply({'ok':True,'crs':aoi_crs(aoi)})
   if self.path=='/dem':
    out=RESULTS/uuid.uuid4().hex;out.mkdir()
    aoi=prepare_aoi(form,out)
    dem=fstr(form,'demsource','copernicus')
    if dem not in ('copernicus','srtm','ign'):raise ValueError('Unknown DEM source')
    if dem in ('copernicus','srtm'):
     from global_dem_downloader import download_copernicus,download_srtm
     buf=float(fstr(form,'buffer_deg','0.05'))
     if not 0<=buf<=2:raise ValueError('Invalid buffer degrees')
     destination=out/('Copernicus_GLO30.tif' if dem=='copernicus' else 'SRTM1.tif')
     if dem=='copernicus':download_copernicus(aoi_path=aoi,out_tif=destination,buffer_deg=buf,plot=False)
     else:download_srtm(aoi_path=aoi,out_tif=destination,buffer_deg=buf,plot=False)
     outputs=[destination]
    else:
     from ign_lidarhd_downloader import download_ign_lidarhd_dsm
     resolution=float(fstr(form,'ign_resolution','5'))
     buf=float(fstr(form,'ign_buffer','1000'))
     if not 0.5<=resolution<=100 or not 0<=buf<=10000:raise ValueError('Invalid IGN settings')
     products=download_ign_lidarhd_dsm(aoi_path=aoi,out_dir=out/'IGN_processing',target_res=resolution,download_buffer=True,buffer_distance_m=buf,n_workers=2,export_to_wgs84=False,plot_results=False)
     outputs=[Path(v) for v in products.values() if str(v).lower().endswith(('.tif','.tiff')) and Path(v).exists()]
     outputs=list(dict.fromkeys(outputs))
    if not outputs or any(not item.is_file() for item in outputs):raise ValueError('DEM provider did not produce raster outputs')
    vertical=fstr(form,'demvertical','native')
    datum=fstr(form,'demdatum',{'copernicus':'egm2008','srtm':'egm96','ign':'raf20'}[dem])
    if vertical not in ('native','ellipsoid'):raise ValueError('Invalid DEM height option')
    if datum not in ('egm2008','egm96','raf20'):raise ValueError('Invalid source vertical datum')
    if vertical=='ellipsoid':
     converted=[]
     for idx,demfile in enumerate(outputs):
      work=out/f'converted_{idx}'
      transformed=raster_process(demfile,work,datum,'ellipsoid',datum)
      for t in transformed:
       t=Path(t)
       name=('DEM_ellipsoidal_' if t.name=='height_converted.tif' else f'{idx}_')+t.name if len(outputs)>1 else ('DEM_ellipsoidal.tif' if t.name=='height_converted.tif' else t.name)
       destination=out/name
       shutil.copy2(t,destination)
       converted.append(destination)
     outputs+=converted
    manifest={'source':dem,'source_vertical_reference_selected':datum,'target_vertical_reference':'ellipsoid' if vertical=='ellipsoid' else 'unchanged','original_v1_downloader':True,'note':'Source datum must be checked in provider metadata. RAF20 conversion only applicable where the height-anomaly grid and NGF-IGN69 are appropriate.'}
    (out/'metadata.json').write_text(json.dumps(manifest,indent=2))
    resultzip=RESULTS/(out.name+'.zip')
    with zipfile.ZipFile(resultzip,'w',compression=zipfile.ZIP_DEFLATED) as z:
     for item in outputs+[out/'metadata.json']:z.write(item,item.name)
    return self.reply({'ok':True,'message':'DEM acquisition completed.','download':'/download/'+resultzip.name,'files':[item.name for item in outputs],'previews':create_previews(outputs,out)})
   mode=fstr(form,'mode')
   out=RESULTS/uuid.uuid4().hex;out.mkdir()
   source=fstr(form,'source','ellipsoid');target=fstr(form,'target','raf20');model=fstr(form,'model','raf20')
   crs=fstr(form,'crs','')
   if not crs and mode not in ('aoi','raster'):crs='EPSG:4326'
   custom=uploaded(form,'custom',out)
   if mode=='aoi':
    aoi=prepare_aoi(form,out)
    crs=output_crs_for_aoi(aoi,crs)
    resolution=float(fstr(form,'resolution','30'))
    if not 0<resolution<1e6:raise ValueError('Invalid raster resolution')
    outputs=aoi_process(aoi,out,crs,resolution,model,custom)
    msg='AOI geoid-separation grid created; NoData outside polygon.'
   elif mode=='raster':
    local_path=fstr(form,'raster_path')
    if local_path:
     raster=Path(local_path.strip().strip('\"').strip("'")).expanduser()
     if not raster.is_file():raise ValueError('Local elevation raster not found. Check its full Windows path: '+str(raster))
     if raster.suffix.lower() not in ('.tif','.tiff'):raise ValueError('Local raster must be a GeoTIFF (.tif or .tiff)')
    else:
     raster=uploaded(form,'raster',out)
    if not raster:raise ValueError('Choose an elevation GeoTIFF or enter its full local path')
    outputs=raster_process(raster,out,source,target,model,custom)
    msg='Raster conversion complete. N rasters provided for applicable models.'
   elif mode=='points':
    raw=fstr(form,'points')
    rows=[]
    for line in raw.splitlines():
     if not line.strip():continue
     vals=[s.strip() for s in line.replace(';',',').split(',')]
     if len(vals) not in (2,3):raise ValueError('Point format: x,y or x,y,z per line')
     rows.append(dict(x=vals[0],y=vals[1],**({'z':vals[2]} if len(vals)==3 and vals[2] else {})))
    if not rows:raise ValueError('Enter at least one point')
    result=point_rows(rows,crs,model,source,target,custom,out/'grid_cache')
    outputs=[out/'points_converted.csv']; save_rows(outputs[0],result)
    msg='Point values calculated.'
   elif mode=='csv':
    file=uploaded(form,'csv',out)
    if not file:raise ValueError('Upload a CSV file')
    with file.open('r',encoding='utf-8-sig',newline='') as stream:
     rdr=csv.DictReader(stream)
     if not rdr.fieldnames:raise ValueError('CSV needs a header')
     original=list(rdr)
    cx=fstr(form,'xcol','x');cy=fstr(form,'ycol','y');cz=fstr(form,'zcol','z')
    if cx not in rdr.fieldnames or cy not in rdr.fieldnames:raise ValueError('Coordinate column missing from CSV')
    rows=[dict(x=r[cx],y=r[cy],**({'z':r[cz]} if cz in rdr.fieldnames and r[cz].strip() else {})) for r in original]
    result=point_rows(rows,crs,model,source,target,custom,out/'grid_cache')
    for old,new in zip(original,result):
     old['geoid_N_m']=new['N_m']
     if 'z_converted_m' in new:old['z_converted_m']=new['z_converted_m']
    outputs=[out/'csv_with_converted_heights.csv'];save_rows(outputs[0],original)
    msg='CSV processed; original columns retained and new columns appended.'
   else:raise ValueError('Select a workflow')
   manifest={'workflow':mode,'model_N':model,'source_vertical':source,'target_vertical':target,'horizontal_CRS':crs,'N_definition':'N = h - H','height_conversion':'z_target = z_source + N_source - N_target','note':'RAF20 is a French quasigeoid height-anomaly model; EGM models are gravity-based global reference models. Verify datum compatibility and required grids.'}
   (out/'metadata.json').write_text(json.dumps(manifest,indent=2))
   resultzip=RESULTS/(out.name+'.zip')
   with zipfile.ZipFile(resultzip,'w',compression=zipfile.ZIP_DEFLATED) as z:
    for p in outputs+[out/'metadata.json']:z.write(p,p.name)
   reply={'ok':True,'message':msg,'download':'/download/'+resultzip.name,'files':[p.name for p in outputs],'previews':create_previews(outputs,out)}
   if mode in ('points','csv'):reply['rows']=(result if mode=='points' else original)[:50]
   self.reply(reply)
  except Exception as ex:
   print('Request failed:',type(ex).__name__,str(ex),flush=True)
   try:self.reply({'ok':False,'error':str(ex)},400)
   except (ConnectionAbortedError,ConnectionResetError,BrokenPipeError):pass
 def log_message(self,fmt,*args):pass

def save_rows(path,rows):
 fields=list(dict.fromkeys(k for r in rows for k in r.keys()))
 with Path(path).open('w',newline='',encoding='utf-8-sig') as f:
  writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader();writer.writerows(rows)

if __name__=='__main__':
 import argparse
 ap=argparse.ArgumentParser();ap.add_argument('--port',type=int,default=8765);ap.add_argument('--no-browser',action='store_true');args=ap.parse_args()
 server=ThreadingHTTPServer(('127.0.0.1',args.port),Handler)
 url=f'http://127.0.0.1:{args.port}/'
 print('Geoid Utility browser interface:',url,flush=True)
 if not args.no_browser:threading.Timer(0.8,lambda:webbrowser.open(url)).start()
 try:server.serve_forever()
 except KeyboardInterrupt:server.server_close()
