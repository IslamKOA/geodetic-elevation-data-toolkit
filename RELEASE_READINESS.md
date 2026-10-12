# v5.0.0 release readiness and publication handoff

**State:** release candidate for the local Python edition; **not yet approved for public distribution**. The Render site is a feature-limited preview and is not the authoritative scientific build.

## Source parity audit (2026-10-12)

Compared the uploaded `geodetic_elevation_data_toolkit_v5.0(1).zip` with GitHub `main` using Git blob SHA-1 for each file. All core local calculation and downloader modules, launch scripts, `requirements.txt`, `CITATION.cff`, `LICENSE`, `NOTICE.md`, RAF20 grid and assets are byte-identical. Changes are in `README.md`, `.gitignore` and `geoid_interface.html`; a new `release_smoke_test.py` was subsequently added. Preserve and review this interface difference before tagging a release.

## Verified checks

The offline check was executed against the uploaded v5.0 package with Python, numpy, rasterio, geopandas, scipy and pyproj installed.

- RAF20 sample at longitude 5.73°, latitude 45.19°, ellipsoidal height 250 m: separation N = 50.54498 m, converted physical height 199.45502 m.
- Raster: small 4×4 WGS84 GeoTIFF, verified `H = h - N` within 0.0001 m and finite output.
- AOI: small GeoJSON polygon near Grenoble, projected to EPSG:32631; nonempty geoid separation output.

**Not yet verified:** independent IGN geodetic control values, EGM96/EGM2008, custom grids, large rasters, clean Windows installation, Copernicus/SRTM/IGN remote downloads, full web deployment, leap-second edge cases. A passing smoke test is not an independent metrological accuracy certificate.

Reproduce: install dependencies in a clean Python environment and run `python release_smoke_test.py` at the repository root.

## Release gates (resolve before public release)

- [ ] Confirm RAF20.tac redistribution terms with IGN; otherwise remove the binary from the public software and document lawful acquisition.
- [ ] Clear institutional logos and the height-reference illustration for redistribution or replace with appropriately licensed artwork.
- [ ] Compare GitHub `geoid_interface.html` with the definitive local GUI and approve one final version.
- [ ] Run a clean Windows Micromamba setup and Linux installation, check port 8765, launchers and browser opening.
- [ ] Validate independent reference control points for RAF20/EGM96/EGM2008 (including vertical datum and CRS assumptions).
- [ ] Test point/CSV, geoid AOI, DEM conversion, custom grid, data downloaders and GPS Time with expected outputs and failures.
- [ ] Review third-party DEM terms, software supply chain, dependency versions, large-dataset resource usage and archive completeness.
- [ ] Prepare numbered release/tag `v5.0.0`, changelog, reproducible example input files, known outputs and checksums.
- [ ] Confirm contributor/author approval and permanent identifiers before updating citation metadata.
- [ ] Approve public visibility of the repository; do not change privacy merely to publish the preview.

## Recommended archiving and data publication

1. GitHub: approved and tagged source release, `CITATION.cff`, license and installation documentation.
2. Software Heritage / HAL: archive and describe the software; record the minted SWHID, HAL identifier or other persistent software identifier.
3. Recherche Data Gouv: publish *associated reproducibility datasets* (input point/CSV/AOI/small DEM where rights permit, reference results, data dictionary, coordinate and vertical reference metadata, QA report). Link records bidirectionally to the software archive and hosted demo. Confirm the institutional collection and metadata requirements with the data steward.

Do not invent a DOI. Add the actual persistent identifiers to `CITATION.cff` and `README.md` after they exist.

## Recommended dataset package manifest

`inputs/` (AOI, point CSV, small DEM) • `expected_outputs/` (reference GeoTIFF/CSV) • `metadata/` (CRS, vertical datum, model version, units, source license and provenance) • `validation_report.pdf` • `README.md` • `checksums.sha256`.

Always keep the *input* vertical datum explicit. The application cannot infer it from numerical elevation values.
