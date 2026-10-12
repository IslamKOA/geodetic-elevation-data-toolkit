# Changelog

## 1.0.1 — 2026-08-23

- Fixed `NameError: name 'math' is not defined` when generating geoid-model
  contour lines.
- No scientific-processing logic or interface defaults changed.


## 1.0.0 — 2026-08-23

- Stable notebook-first Reference DEM Utility.
- One final DEM output.
- Copernicus GLO-30, SRTM1, IGN LiDAR HD and Existing DEM modes.
- Explicit WGS 84 / EPSG:4326 output option.
- Automatic local projected CRS and custom CRS support.
- Optional geoid ↔ ellipsoid conversion.
- France defaults to RAF20 when conversion is enabled, with editable model.
- EGM96, EGM2008 and custom N-raster support.
- Geoid separation raster saving and visualization.
- Terrain-style geoid colorbar with labeled contours.
- Robust no-data validation to prevent blank DEM/model results from being
  reported as successful.
- Automatic installation of missing Python dependencies in the notebook.
