"""Regression checks for ElevDatum source updates, without network or Conda."""
import importlib.util
import json
import pathlib
import py_compile
import tempfile
import unittest
import zipfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("elevdatum_update", ROOT / "elevdatum_update.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class UpdateTests(unittest.TestCase):
    def archive(self, path, suffix, extra=None):
        files = {
            "geoid_web.py": f"print({suffix!r})\n",
            "geoid_engine.py": "x = 1\n",
            "geoid_interface.html": f"<title>{suffix}</title>",
            "requirements.txt": "numpy\n",
            "Reference_DEM_Utility.ipynb": '{"cells": [], "metadata": {}, "nbformat": 4, "nbformat_minor": 5}',
        }
        files.update(extra or {})
        with zipfile.ZipFile(path, "w") as z:
            for name, body in files.items():
                z.writestr("geodetic-elevation-data-toolkit-main/" + name, body)

    def test_refresh_updates_scripts_ui_notebook_and_preserves_user_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            folder = root / "installation"
            archive = root / "source.zip"
            self.archive(archive, "first")
            module.update(archive, folder, "test")
            (folder / "my_custom_results.csv").write_text("personal data")
            self.archive(archive, "second", {"new_module.py": "value = 2\n"})
            module.update(archive, folder, "test")
            self.assertIn("second", (folder / "geoid_web.py").read_text())
            self.assertIn("second", (folder / "geoid_interface.html").read_text())
            self.assertTrue((folder / "Reference_DEM_Utility.ipynb").is_file())
            self.assertTrue((folder / "new_module.py").is_file())
            self.assertEqual((folder / "my_custom_results.csv").read_text(), "personal data")
            self.assertIn("new_module.py", json.loads((folder / module.MANIFEST).read_text())["files"])

    def test_invalid_archive_does_not_modify_existing_installation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            folder = root / "installation"
            archive = root / "source.zip"
            self.archive(archive, "working")
            module.update(archive, folder, "test")
            self.archive(archive, "invalid", {"broken.py": "def fails(:\n"})
            with self.assertRaises(py_compile.PyCompileError):
                module.update(archive, folder, "test")
            self.assertIn("working", (folder / "geoid_web.py").read_text())

if __name__ == "__main__":
    unittest.main()
