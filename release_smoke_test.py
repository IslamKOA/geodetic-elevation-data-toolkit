"""Run from repository root: python release_smoke_test.py.
Deterministic offline test of the unchanged RAF20 scientific engine.
"""
from pathlib import Path
from tempfile import TemporaryDirectory
import numpy as np
import rasterio
from rasterio.transform import from_origin
from geoid_engine import point_rows, aoi_process, raster_process

ROOT=Path(__file__).resolve().parent
assert (ROOT/"data"/"RAF20.tac").is_file(), "RAF20 grid missing"
point=point_rows([{"x":"5.73","y":"45.19","z":"250"}],
                 "EPSG:4326","raf20","ellipsoid","raf20")[0]
assert np.isfinite(point["N_m"])
assert abs(250-point["N_m"]-point["z_converted_m"])<2e-4
print("RAF20 Grenoble point:",point["N_m"],point["z_converted_m"])
with TemporaryDirectory() as td:
    d=Path(td)
    with rasterio.open(d/"input.tif","w",driver="GTiff",width=4,height=4,
        count=1,dtype="float32",crs="EPSG:4326",
        transform=from_origin(5.729,45.191,0.0005,0.0005),nodata=-9999) as ds:
        ds.write(np.full((4,4),250,dtype="float32"),1)
    raster_process(d/"input.tif",d/"raster","ellipsoid","raf20","raf20")
    with rasterio.open(d/"raster"/"height_converted.tif") as height, rasterio.open(d/"raster"/"N_raf20.tif") as n:
        assert height.crs==n.crs and height.width==4
        assert np.all(np.isfinite(height.read(1)))
        assert np.allclose(height.read(1),250-n.read(1),atol=1e-4)
    aoi='{"type":"FeatureCollection","features":[{"type":"Feature","properties":{},"geometry":{"type":"Polygon","coordinates":[[[5.729,45.189],[5.731,45.189],[5.731,45.191],[5.729,45.191],[5.729,45.189]]]}}]}'
    (d/"aoi.geojson").write_text(aoi,encoding="utf-8")
    product=aoi_process(d/"aoi.geojson",d/"aoi_out","EPSG:32631",30,"raf20")
    with rasterio.open(product[0]) as ds:
        assert ds.crs.to_epsg()==32631 and ds.read(1,masked=True).count()>0
print("PASS: RAF20 point, raster and AOI computation.")
