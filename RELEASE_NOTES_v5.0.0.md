# v5.0.0 — Local Geodetic & Elevation Data Toolkit

This release documents the locally installable toolkit. The Render-hosted demonstration provides selected RAF20 workflows and GPS Time, with resource and model limitations; the complete workflow set is available in the local edition.

## Features
- Geoid / height-anomaly AOI raster generation.
- Ellipsoidal / physical-height raster conversion.
- Survey point and CSV conversion with explicit coordinate reference systems.
- French RAF20 and EGM96 / EGM2008 geodetic models, subject to grid availability and coverage; user-provided custom separation rasters.
- Copernicus / SRTM / IGN DEM acquisition tools, subject to upstream availability and data provider terms.
- GPS time utility and graphical result preview.
- Windows launcher, Linux/macOS launcher and a browser-based local interface.

## Reproducible installation
1. Download the `main` branch source ZIP and extract.
2. Install Python and execute `python -m pip install -r requirements.txt` in a dedicated environment.
3. On Windows, run `START_WINDOWS.bat`; on Linux/macOS run `sh START_LINUX_MAC.sh`.
4. Alternatively run `python geoid_web.py` and visit `http://127.0.0.1:8765/`.
5. Execute `python release_smoke_test.py` for the repeatable offline RAF20 regression check.

## Verified checks and limitations
- User reports successful operation on their Windows machine.
- GitHub Actions on `main` passed the offline RAF20 point/raster/AOI smoke tests.
- These are functionality and internal equation-consistency tests, **not** independent EGM96/EGM2008 or RAF20 metrological reference certifications.
- Geoid/quasigeoid model, vertical datum and coverage must be checked for each input raster.
- Installation packages depend on external Python libraries and official data providers.

## Reproducibility and third-party attribution
- The bundled IGN `RAF20.tac`, institutional logos, illustrations, optional geodetic grids and downloaded DEMs retain their original licensing conditions; consult [NOTICE.md](NOTICE.md) and the relevant data providers. The CeCILL-B source license does not grant rights to third-party materials.
- The software cannot infer the source DEM's vertical datum: users must identify it from metadata before selecting a transformation.
- Exact model-grid provenance, CRS realization and numeric validation must be documented for scientific use.

## Citation and permanent archiving
See [CITATION.cff](CITATION.cff) for software citation details. Upon publication, a tagged source release may be archived with Software Heritage/HAL, and corresponding reproducibility datasets may be deposited in Recherche Data Gouv. Add persistent identifiers only when officially assigned.
