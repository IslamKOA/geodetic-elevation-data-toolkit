"""Prevent old ElevDatum branding or interface release labels from returning.

The published v5.0.0 tag remains immutable; the Windows installer applies a
presentation-only patch to the installed tagged source.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ElevDatumBrandingTests(unittest.TestCase):
    def test_source_displays_current_scientific_release(self):
        html = (ROOT / "geoid_interface.html").read_text(encoding="utf-8")
        self.assertIn("<title>ElevDatum | Geodetic & Elevation Data Toolkit</title>", html)
        self.assertIn("<h1>ElevDatum</h1>", html)
        self.assertIn("Research software · v5.0.0", html)
        self.assertNotIn("Research software · v2.4", html)

    def test_windows_installer_keeps_published_release_and_one_browser_open(self):
        installer = (ROOT / "INSTALL_WINDOWS_AUTO.ps1").read_text(encoding="utf-8")
        self.assertIn('$release = "v5.0.0"', installer)
        self.assertIn('geoid_web.py --no-browser', installer)
        self.assertIn('Research software[^<]*?v', installer)
        self.assertIn("v5.0.0</div>", installer)


if __name__ == "__main__":
    unittest.main()
