"""Hosted point API smoke tests. Run: python -m unittest discover -s tests"""
import os
import unittest
from unittest.mock import patch
os.environ["WEB_ENABLE_POINTS"]="1"
from web_preview import app

class PointApiTests(unittest.TestCase):
    def setUp(self):
        self.client=app.test_client()
    def test_health(self):
        self.assertEqual(self.client.get("/health").status_code,200)
    def test_dem_disabled(self):
        self.assertEqual(self.client.post("/dem").status_code,503)
    def test_raster_disabled(self):
        self.assertEqual(self.client.post("/run",data={"mode":"raster"}).status_code,503)
    def test_egm_disabled(self):
        self.assertEqual(self.client.post("/run",data={"mode":"points","points":"2,45","model":"egm96"}).status_code,503)
    def test_invalid_point(self):
        self.assertEqual(self.client.post("/run",data={"mode":"points","points":"abc,45"}).status_code,400)
    @patch("web_points.point_rows",return_value=[{"x":"2","y":"45","N_m":47.0}])
    def test_results_and_download(self, mocked):
        r=self.client.post("/run",data={"mode":"points","points":"2,45","model":"raf20"})
        self.assertEqual(r.status_code,200)
        download=self.client.get(r.json["download"])
        self.assertEqual(download.status_code,200)
        self.assertTrue(download.data.startswith(b"PK"))
        self.assertEqual(self.client.get(r.json["download"]).status_code,404)
if __name__=="__main__": unittest.main()
