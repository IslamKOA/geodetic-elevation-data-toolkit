# v5.0.0 — Local Geodetic & Elevation Data Toolkit

**Release status: prepared, not published.** This release note describes the local installable software on the `main` branch. The Render-hosted website is a limited preview, not a substitute for the full local edition.

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

## Release-blocking prerequisites
- Confirm that the bundled IGN `RAF20.tac`, the embedded institutional logos and diagrams may be redistributed in this repository under their own terms.
- Approve the final interface: the GitHub `geoid_interface.html` differs from the original uploaded v5.0 ZIP.
- Ensure the README and citation metadata match the exact tagged release and document the EGM grid provenance.
- Record known numerical validation limitations in the public release description.

## Publication handoff
After approval, tag the reviewed commit `v5.0.0`, create a GitHub Release using this text, verify its automatically generated source ZIP, and archive the source in Software Heritage/HAL. Record actual persistent identifiers when they exist. Publish associated licensed test data and reproducibility results separately via Recherche Data Gouv.

Do not make the repository public or claim a DOI without the owner's approval and completed redistribution review.
