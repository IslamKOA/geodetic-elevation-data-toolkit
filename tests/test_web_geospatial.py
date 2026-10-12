"""End-to-end hosted geospatial tests against original RAF20 scientific engine."""
import io
import json
import os
import unittest
import zipfile
from unittest.mock import patch
os.environ["WEB_ENABLE_POINTS"]="1"
os.environ["WEB_ENABLE_GEO"]="1"
from web_preview import app

class GeoTests(unittest.TestCase):
    def setUp(self):
        self.client=app.test_client()
    def aoi(self):
        # Small polygon near Grenoble, explicitly WGS84.
        geom={"type":"FeatureCollection","features":[{"type":"Feature","geometry":{
            "type":"Polygon","coordinates":[[[5.729,45.189],[5.731,45.189],[5.731,45.191],[5.729,45.191],[5.729,45.189]]]},
            "properties":{}}]}
        data=json.dumps(geom).encode("utf8")
        return io.BytesIO(data),"test.geojson"
    def test_inspect_crs(self):
        r=self.client.post("/inspect",data={"aoi_parts":self.aoi()})
        self.assertEqual(r.status_code,200,r.get_data(as_text=True))
        self.assertIn("4326",r.json["crs"])
    def test_aoi_real_output(self):
        r=self.client.post("/run",data={"mode":"aoi","model":"raf20","resolution":"30","aoi_parts":self.aoi()})
        self.assertEqual(r.status_code,200,r.get_data(as_text=True))
        z=self.client.get(r.json["download"])
        self.assertEqual(z.status_code,200)
        with zipfile.ZipFile(io.BytesIO(z.data)) as archive:
            self.assertIn("geoid_separation_N_raf20.tif",archive.namelist())
    def test_block_local_path(self):
        r=self.client.post("/run",data={"mode":"raster","model":"raf20","raster_path":"/etc/passwd"})
        self.assertEqual(r.status_code,503)
    def test_egm_disabled(self):
        r=self.client.post("/run",data={"mode":"aoi","model":"egm2008","aoi_parts":self.aoi()})
        self.assertEqual(r.status_code,503)
    def test_raster_real_output(self):
        import rasterio
        import numpy as np
        from rasterio.io import MemoryFile
        from rasterio.transform import from_origin
        with MemoryFile() as file:
            with file.open(driver="GTiff",height=4,width=4,count=1,dtype="float32",
                transform=from_origin(5.729,45.191,0.0005,0.0005),
                crs="EPSG:4326") as ds:
                ds.write(np.full((4,4),250,dtype="float32"),1)
            data=file.read()
        r=self.client.post("/run",data={"mode":"raster","model":"raf20","source":"ellipsoid","target":"raf20",
            "raster":(io.BytesIO(data),"input.tif")})
        self.assertEqual(r.status_code,200,r.get_data(as_text=True))
        z=self.client.get(r.json["download"])
        self.assertEqual(z.status_code,200)
        with zipfile.ZipFile(io.BytesIO(z.data)) as archive:
            self.assertIn("height_converted.tif",archive.namelist())
            with MemoryFile(archive.read("height_converted.tif")) as file:
                with file.open() as ds:
                    v=ds.read(1)
                    self.assertTrue(np.all(np.isfinite(v)))
                    self.assertTrue(np.all(v<250))
if __name__=="__main__":unittest.main()
