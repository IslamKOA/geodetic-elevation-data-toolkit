## Unreleased — ElevDatum desktop shortcut naming and installation documentation

- Changed the automatic Windows installer to create the Desktop shortcut as **ElevDatum** (`ElevDatum.lnk`) while preserving the existing command launcher, geospatial Python environment, data paths and v5.0.0 scientific code.
- Standalone ED icon refresh now renames the prior `Geodetic Elevation Toolkit.lnk` shortcut when no conflicting `ElevDatum.lnk` exists. The full installer also removes a redundant legacy shortcut only if it targets the same launcher.
- Audited the README against the Windows and Linux/macOS scripts: one-command first-time installs, automatic Micromamba bootstrapping, icon-only refresh, and honest distinction between rerunning an installer and updating immutable scientific source code.
- Corrected the Linux/macOS ZIP installation for systems where the temporary directory and home folder reside on different filesystems.
- Retained the published DOI and `v5.0.0` source archive without altering numerical processing.

## Unreleased — No-prerequisite ElevDatum installation (Windows, Linux and macOS)

- Windows `INSTALL_WINDOWS_AUTO.ps1` now works without preinstalled Conda, Micromamba, Mamba, Python or Git: it discovers existing managers even when not on PATH and, if needed, downloads the official standalone Micromamba executable directly into the user's local application directory.
- The installer creates a dedicated `geoid_tool` environment with Python 3.12 and geospatial dependencies only if missing, verifies the real managed Python and packages, reuses healthy environments, and leaves broken existing environments untouched rather than silently overwriting them.
- Added `INSTALL_LINUX_MAC_AUTO.sh` to bootstrap Micromamba and Python and install the same published v5.0.0 software from a ZIP on Linux and macOS without a preinstalled environment or Git.
- Kept the scientific source pinned to the original v5.0.0 release, preserved original launch paths and project data, and retained the separate automatic ElevDatum ED desktop icon updater on Windows.
- Updated README and manual guides to recommend the one-command installers and explain optional manual alternatives.

## Unreleased — ElevDatum ED visual identity and desktop shortcut

- Added the approved ED/Earth/DEM concept as the official ElevDatum logo; the public README uses a small right-aligned thumbnail.
- Added a standalone `SET_ELEVDATUM_ICON.ps1` to apply the branded icon to an existing Windows Desktop shortcut without changing the launcher target, its environment, source files or scientific processing.
- The existing Windows installer now retrieves the icon helper from the current branch after creating its shortcut; this works with the pinned stable v5.0.0 download and does not modify the historical release tag.
- Documentation explains the new visible ElevDatum brand while retaining the original v5.0.0 research-software DOI and published citation title.
- The repository renaming to `elevdatum` is a separate GitHub Settings operation; the updater recognizes both the intended new and existing repository addresses.

## v5.0.0 — 2026-10-12
- Full user-guide audit and rewrite covering every interface panel, inputs, outputs, installation, limitations, and troubleshooting.
- Updated version identifiers to 5.0.0 and kept CeCILL-B attribution and program calculations unchanged.
- Removed publication-planning guide from this local-use release; no publication identifier assigned.

## v4.0.0 — 2026-10-08
- Rebased v4.0.0 directly on the user-provided working v3.6.0 package.
- Preserved the original CeCILL-B license and third-party notices (no relicensing).
- Updated release version in HTML, citation metadata and documentation.
- Preserved existing processing, downloader and GPS Time implementations.

## v3.6.0 — 2026-10-08
- Added 06 · GPS Time panel using the original Convert_GPStime.html as a reference.
- Added standard GPS seconds, GPS week/seconds-of-week, UTC ISO 8601, Unix seconds and legacy GPS-minus-1e9 inputs.
- Applied historical leap-second schedule through the latest embedded 2017 change; leap-second instants flagged.
- Preserved geoid, raster, points/CSV and DEM workflows and overview-only licensing.

## v3.1
- Improved IGN WFS error extraction and alternative CRS/BBOX request encodings.
- Provides official IGN MNS download portal fallback.
- Live IGN service access was not available for testing.

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
## v2.2
- Improved HTML interface design with embedded institutional logos.
- Added developer attribution and supervisors: Alain Recking and Laurent Borgniet.
- Refined header, spacing, tabs, and overall visual layout while preserving processing logic.


## v2.3
- Added 00 Scientific overview with geoid concept illustration, conversion equations, navigation cards, references.
- Compact developer/supervisor attribution and refined institutional header.
- Preserved computation and DEM downloader backend.

## v2.5
- Added direct multi-file shapefile selection (.shp, .shx, .dbf, .prj), alongside zipped shapefiles, GeoJSON, and GeoPackage.
- Added AOI CRS inspection endpoint and automatic projected-CRS selection for raster outputs. Geographic AOIs automatically use local UTM when output CRS is left blank.
- Added clearer connection-failure messages and removed Local Geospatial Utility badge.

## v2.7
- Add on-page PNG raster previews and compact statistics after AOI, raster and DEM processing.
- Add tabular previews for point and CSV conversions (up to 50 rows).
- Preserve original scientific rasters and ZIP downloads unchanged.
## v2.8
- Added raster preview coordinate axes based on the raster/output CRS.
- Added light preview grids and contour-line overlays with labels for easier inspection.
- Improved preview readability for AOI geoid grids, converted DEMs, and elevation rasters.


## v2.9
- Added direct local-file path raster processing for large GeoTIFFs, bypassing 400 MB browser upload cap.
- Added clear size error message in the interface and server.

## v3.0
- Fixed raster converter UnboundLocalError caused by a nested raster_process import.
- Added IGN WFS request fallbacks and service error detail reporting (HTTP 400).
- Verified local path raster conversion, RAF20 separation output and previews.
- IGN download requires live validation on client machine.

## v3.2
- Replaced IGN MNS downloader with the implementation from the supplied Pléiades ASP workflow.
- Added direct IGN WMS-raster fallback for unavailable WFS tile-index namespaces.
- Updated WFS layer discovery, tile construction, and download retries.
- Live service downloading has not been independently verified in this environment.

## v3.4
- Updated the application title to **Geodetic & Elevation Data Toolkit**; processing functions preserved from v3.3.

## 3.5.0
- Added CeCILL-B software license matching the Pléiades ASP Workflow.
- Updated CITATION.cff and included notices and publication instructions.
- Added license, citation and supervisor credits to the HTML interface.
