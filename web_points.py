"""Bounded point/CSV API for the hosted scientific preview.

Only ellipsoid and RAF20 are enabled initially; EGM downloading, custom grids,
arbitrary file paths and user-supplied raster processing are not invoked here.
"""
import csv
import io
import json
import math
import secrets
import threading
import time
import zipfile
from flask import Blueprint, jsonify, request, Response
from geoid_engine import point_rows

points_api = Blueprint("hosted_points", __name__)
_LOCK = threading.BoundedSemaphore(1)
_DOWNLOADS = {}
_STORE_LOCK = threading.Lock()
_TTL = 180
_MAX_ROWS = 100
_MODELS = {"ellipsoid", "raf20"}

def _error(message, status=400):
    return jsonify(ok=False, error=message), status

def _text(name, default=""):
    value = request.form.get(name, default)
    if not isinstance(value, str) or len(value) > 128:
        raise ValueError("Invalid form value")
    return value.strip()

def _validate_rows(rows):
    if not rows or len(rows)>_MAX_ROWS:
        raise ValueError(f"Enter between 1 and {_MAX_ROWS} points.")
    for row in rows:
        if any(k not in row for k in ("x", "y")):
            raise ValueError("Coordinates must include x and y.")
        for key in ("x", "y", "z"):
            if key in row and str(row[key]).strip():
                if not math.isfinite(float(row[key])):
                    raise ValueError("Coordinates and heights must be finite numbers.")
    return rows

def _to_zip(filename, rows, metadata):
    stream=io.StringIO(newline="")
    cols=list(dict.fromkeys(k for row in rows for k in row.keys()))
    writer=csv.DictWriter(stream, fieldnames=cols)
    writer.writeheader()
    writer.writerows(rows)
    out=io.BytesIO()
    with zipfile.ZipFile(out,"w",compression=zipfile.ZIP_DEFLATED) as arc:
        arc.writestr(filename,stream.getvalue().encode("utf-8-sig"))
        arc.writestr("metadata.json",json.dumps(metadata,indent=2))
    return out.getvalue()

@points_api.post("/run")
def run_points():
    geo_requested = request.form.get("mode") in {"aoi", "raster"} and __import__("os").environ.get("WEB_ENABLE_GEO") == "1"
    max_size = 12*1024*1024 if geo_requested else 256*1024
    if request.content_length is None or request.content_length>max_size:
        return _error("Request exceeds the hosted size limit.",413)
    if not _LOCK.acquire(blocking=False):
        return _error("A conversion is in progress. Try again shortly.",503)
    try:
        mode=_text("mode")
        if mode in {"aoi", "raster"} and __import__("os").environ.get("WEB_ENABLE_GEO") == "1":
            from web_geospatial import run_geo
            return run_geo()
        if mode not in {"points","csv"}:
            return _error("This hosted preview currently accepts only manual points or CSV; use the local edition for raster and AOI processing.",503)
        model=_text("model","raf20").lower()
        source=_text("source","ellipsoid").lower()
        target=_text("target","raf20").lower()
        if any(value not in _MODELS for value in (model,source,target)):
            return _error("Hosted points currently support RAF20 and ellipsoidal references only. EGM/custom grids require further validation.",503)
        crs=_text("crs","EPSG:4326") or "EPSG:4326"
        from pyproj import CRS
        parsed_crs=CRS.from_user_input(crs)
        if not parsed_crs.is_projected and not parsed_crs.is_geographic:
            raise ValueError("Use a projected or geographic horizontal CRS.")
        if mode=="points":
            raw=request.form.get("points","")
            if len(raw)>12000: raise ValueError("Too many point characters.")
            rows=[]
            for line in raw.splitlines():
                if not line.strip():continue
                vals=[p.strip() for p in line.replace(";",",").split(",")]
                if len(vals) not in (2,3): raise ValueError("Use x,y or x,y,z per line.")
                rows.append(dict(x=vals[0],y=vals[1],**({"z":vals[2]} if len(vals)==3 and vals[2] else {})))
            _validate_rows(rows)
            original=None
        else:
            uploaded=request.files.get("csv")
            if not uploaded or not uploaded.filename.lower().endswith(".csv"):
                raise ValueError("Upload a .csv file.")
            data=uploaded.read(128*1024+1)
            if len(data)>128*1024:raise ValueError("CSV exceeds 128 KB.")
            reader=csv.DictReader(io.StringIO(data.decode("utf-8-sig")))
            if not reader.fieldnames or len(reader.fieldnames)>60:raise ValueError("Invalid CSV header.")
            original=list(reader)
            if len(original)>_MAX_ROWS:raise ValueError("CSV exceeds 100 rows.")
            xcol=_text("xcol","x");ycol=_text("ycol","y");zcol=_text("zcol","z")
            if xcol not in reader.fieldnames or ycol not in reader.fieldnames:
                raise ValueError("CSV coordinate columns not found.")
            rows=[dict(x=r[xcol],y=r[ycol],**({"z":r[zcol]} if zcol in r and r[zcol].strip() else {})) for r in original]
            _validate_rows(rows)
        # RAF20 interpolation is regional; the existing engine rejects points outside coverage.
        result=point_rows(rows,crs,model,source,target,custom=None,cache=None)
        if original is None:
            output=result
            filename="points_converted.csv"
        else:
            for old,new in zip(original,result):
                old["geoid_N_m"]=new["N_m"]
                if "z_converted_m" in new:old["z_converted_m"]=new["z_converted_m"]
            output=original
            filename="csv_with_converted_heights.csv"
        meta=dict(workflow=mode,model_N=model,source_vertical=source,target_vertical=target,
                  horizontal_CRS=crs,N_definition="N = h - H",
                  caution="RAF20 is region- and datum-specific; validate results against control points.")
        token=secrets.token_urlsafe(24)
        archive=_to_zip(filename,output,meta)
        now=time.time()
        with _STORE_LOCK:
            for key,(ts,_) in list(_DOWNLOADS.items()):
                if now-ts>_TTL: _DOWNLOADS.pop(key,None)
            if len(_DOWNLOADS)>=20:
                oldest=min(_DOWNLOADS,key=lambda k:_DOWNLOADS[k][0])
                _DOWNLOADS.pop(oldest,None)
            _DOWNLOADS[token]=(now,archive)
        return jsonify(ok=True,message="Hosted point conversion complete.",
            rows=output[:50],files=[filename],download="/download/"+token,previews=[])
    except (ValueError,TypeError,KeyError,UnicodeError) as exc:
        return _error(str(exc))
    except Exception:
        return _error("Conversion failed. Verify geographic coverage, datum, coordinate CRS, and inputs.")
    finally:
        _LOCK.release()

@points_api.get("/download/<token>")
def download(token):
    if len(token)>128:return _error("Invalid download.",404)
    with _STORE_LOCK:
        entry=_DOWNLOADS.pop(token,None)
    if entry is None or time.time()-entry[0]>_TTL:
        return _error("Download expired; rerun the conversion.",404)
    return Response(entry[1],mimetype="application/zip",
        headers={"Content-Disposition":"attachment; filename=geodetic_points_results.zip",
                 "Cache-Control":"no-store"})
