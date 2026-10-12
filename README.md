# Geodetic & Elevation Data Toolkit

**Geoid and vertical datum transformations · DEM acquisition · Survey coordinates · GPS time**

**Version:** 5.0.0 · **Developer:** Islam KOA · **Supervisors:** Alain Recking and Laurent Borgniet  
**Research affiliations:** Université Grenoble Alpes, INRAE ETNA, and An-Najah National University  
**Source-code license:** [CeCILL-B](LICENSE) · [Attribution and third-party notices](NOTICE.md)

![Ellipsoidal height, physical height, and geoid/quasigeoid separation concept](assets/Geoid_concept.png)

*Geodetic height-reference concept. Illustration bundled with the toolkit; see [third-party material notices](NOTICE.md).*

**Validation and reproducibility:** [Scientific smoke test](release_smoke_test.py) · [Validation and publication notes](RELEASE_READINESS.md). The local installation is the reference implementation; the hosted website is a limited demonstration.

## What can this toolkit do?

The toolkit connects **a chosen area, an existing DEM, survey coordinates, or a newly downloaded DEM** to geoid/quasigeoid modelling and height-reference conversion. Users can obtain a model separation grid, transform elevations between compatible vertical references, or retrieve a reference DEM and optionally convert its heights.

| Starting point | What you can do | Result |
| --- | --- | --- |
| **Area of interest (AOI)** | Delimit a polygon and calculate geoid/quasigeoid separation over the area using RAF20, EGM96, EGM2008, or a compatible custom GeoTIFF model | Separation raster (GeoTIFF), map preview, metadata |
| **Existing elevation raster (DEM/DSM)** | Convert ellipsoidal heights **h** to model-consistent physical heights **H**, reverse the conversion, or transform between compatible height references | Converted GeoTIFF, separation grid(s), previews |
| **Survey points or CSV** | Enter coordinates (with optional elevations) or import a CSV; calculate separation and converted elevations while retaining input fields | Point results or enriched CSV |
| **DEM not yet available** | Request Copernicus GLO-30, SRTM1, or IGN LiDAR HD DSM for an AOI, with optional conversion to ellipsoidal heights | Downloaded DEM and, when selected, converted DEM |
| **LiDAR / GNSS GPS timestamps** | Convert an extracted GPS-time value or GPS week + seconds-of-week to UTC and Unix time; inspect a sequence of timestamps to help identify acquisition dates/times | Human-readable UTC time and GPS/Unix equivalents |
| **Advanced reference DEM work** | Browse the source notebook and scripts for DEM preparation, reprojection, and QC | [Advanced / Legacy source code](advanced_legacy/) |

### Web version and desktop version

**[Open the hosted website (web preview)](https://geodetic-elevation-toolkit-preview.onrender.com)**

The hosted preview provides GPS Time and bounded **RAF20 AOI/geoid-grid, elevation-raster and point/CSV processing**. Online file-size, pixel-count and model restrictions apply, and **DEM acquisition, EGM96/EGM2008 and custom-grid processing remain available through the local installation rather than this hosted preview**. The **local version provides the full set of processing workflows** described below, subject to external service, model-grid and data availability.

**[Download source code (ZIP)](https://github.com/IslamKOA/geodetic-elevation-data-toolkit/archive/refs/heads/main.zip)** · [Browse source](https://github.com/IslamKOA/geodetic-elevation-data-toolkit) · [Changelog](CHANGELOG.md)

> **Availability:** Download and installation links work when repository access is granted. The separately hosted website is a limited preview. Dataset and image redistribution remains subject to the original rights holders' terms; see [NOTICE.md](NOTICE.md).

### Install locally (Windows)

1. Download the source ZIP above and **extract** it.
2. Install [Micromamba](https://mamba.readthedocs.io/en/latest/user_guide/micromamba.html) if not already installed; create the environment once in PowerShell:

   ```powershell
   micromamba create -n geoid_tool -c conda-forge python=3.12 numpy scipy rasterio geopandas pyproj requests matplotlib pandas shapely affine -y
   ```

3. Open a terminal with the `geoid_tool` environment activated, then navigate to the extracted folder containing `geoid_web.py`. Example:

   ```powershell
   micromamba activate geoid_tool
   cd "C:\Users\YourName\Downloads\geodetic-elevation-data-toolkit-main"
   python geoid_web.py
   ```

4. Open **http://127.0.0.1:8765/** in your browser and keep the terminal open.

**No manual `cd` when using the launcher:** `START_WINDOWS.bat` already executes `cd /d "%~dp0"` and changes automatically to the directory in which it resides. Double-click it **after** Python and its dependencies have been installed in an environment the launcher can discover. If it cannot discover your Micromamba environment, use steps 2–4 instead. Do not double-click `geoid_interface.html` alone: scientific processing needs the local Python server.

For Linux/macOS, see [Installation and launch](#installation-and-launch) below.

### LiDAR GPS time: interpreting acquisition timestamps

The GPS Time panel is useful when reviewing **GPS-time attributes extracted from airborne LiDAR LAS/LAZ point clouds** to estimate the acquisition instant of individual points and the start/end of flight data coverage. First confirm from the LAS header and data provider whether the field is **GPS Week Time** or **Adjusted Standard GPS Time**. In LAS, adjusted standard GPS time has an offset of **1,000,000,000 seconds**; apply the appropriate input convention in the toolkit. GPS Week Time alone requires the correct GPS week (or sufficient flight metadata to establish it), and GPS time is not automatically UTC because leap seconds differ. **The tool converts time values; it does not open LAS/LAZ files, discover flight metadata, or independently establish the exact flight time without correctly interpreted input timestamps.** Check time zone, source metadata, and the leap-second table before using results.

### How to cite this software

If you use the toolkit for geoid modelling, DEM processing, coordinate conversion, or LiDAR/GNSS time interpretation in a publication, thesis, report, or project, please cite:

> **Koa, I. (2026).** *Geodetic & Elevation Data Toolkit* (Version 5.0.0) [Computer software]. GitHub. https://github.com/IslamKOA/geodetic-elevation-data-toolkit

**BibTeX:**

```bibtex
@software{koa_geodetic_elevation_toolkit_2026,
  author  = {Koa, Islam},
  title   = {Geodetic & Elevation Data Toolkit},
  year    = {2026},
  version = {5.0.0},
  url     = {https://github.com/IslamKOA/geodetic-elevation-data-toolkit},
  note    = {Geoid and vertical datum transformations, DEM acquisition and GPS time conversion}
}
```

GitHub also displays **“Cite this repository”**, generated from [CITATION.cff](CITATION.cff). **A DOI has not yet been assigned.** If an archival DOI is registered later, the citation can be updated to include it. Cite the version actually used and, where appropriate, separately cite the original geodetic and elevation datasets.

---

## Overview

The Geodetic & Elevation Data Toolkit is a local, browser-operated geospatial application for geoid/quasigeoid separation, vertical-height transformation, raster and coordinate conversion, reference DEM acquisition, and GPS time conversion. Its HTML interface communicates with a **Python server on the same computer**; the source files are processed locally. It is not a standalone offline HTML calculator. A separate hosted preview offers a restricted subset; full scientific workflows currently require the local installation.

### Feature index

| Interface | Supported features | Outputs / display |
| --- | --- | --- |
| **00 · Overview** | Geodetic concepts, height-reference equations, workflow navigation, credits and license | Scientific explanation and interface shortcuts |
| **01 · AOI geoid grid** | Polygon AOI upload, source-CRS detection, automatic projected output CRS or explicit EPSG override, user-chosen pixel size, RAF20/EGM96/EGM2008/custom model | GeoTIFF separation grid (`geoid_separation_N_<model>.tif`) and map preview; outside AOI is NoData |
| **02 · Elevation raster** | Single-band GeoTIFF; ellipsoidal ↔ physical-height conversion, model-to-model conversion where supported; original raster CRS, grid and NoData retained; optional local path for large rasters | Converted `height_converted.tif`, model separation raster(s), metadata, PNG previews and ZIP |
| **03 · Points & CSV** | Type one or more `x,y` / `x,y,z` records, or load CSV and specify coordinate/elevation columns; choose input horizontal CRS and vertical references | Point or CSV output containing separation `N` and optional converted `z`; original CSV columns retained; table preview |
| **05 · DEM downloads** | Fetch Copernicus GLO-30, SRTM1, or IGN LiDAR HD DSM for an AOI; source-specific buffer/resolution settings; optionally convert downloaded elevations to ellipsoidal heights | Downloaded GeoTIFF(s), optional ellipsoidal DEM and separation raster, metadata, previews, downloadable ZIP |
| **06 · GPS Time** | GPS seconds, GPS week + seconds of week, UTC ISO 8601, Unix seconds and legacy GPS-minus-1-billion inputs | Converted UTC, Unix and GPS values, GPS week, seconds of week, GPS−UTC offset |
| **Advanced / legacy** | Original reference-DEM preparation scripts and notebook | Additional DEM preparation, reprojection, plotting and quality checks |

*The interface numbering follows the existing application (there is no “04” tab).*

## Supported geodetic models and conversions

- **RAF20**: regional French quasigeoid/height-anomaly model for the RGF93–NGF-IGN69 relationship, subject to its geographic and datum applicability.
- **EGM96**: global separation model; may require the corresponding PROJ vertical grid.
- **EGM2008**: global separation model; may require the corresponding PROJ vertical grid.
- **Custom geoid grid**: user-supplied GeoTIFF storing the separation `N` in metres; visible as an upload option **only** when a custom model is selected.
- **Height conversions**: ellipsoidal to physical heights, physical to ellipsoidal heights, or between compatible vertical-reference models. **The tool cannot infer an input DEM's vertical datum from its pixel values.**

For applicable models the software uses `N = h − H`, so:

```text
h = H + N
H = h − N
z_target = z_source + N_source − N_target
```

All heights and separation values are in **metres**. Here `N` is a general separation symbol: RAF20 is a height-anomaly surface rather than an interchangeable worldwide geoid. The reference ellipsoid, regional vertical datum and model realization must agree with the source data.

## Workflow instructions

### 00 — Overview

Read the scientific summary, formulas, processing-panel descriptions, software attribution and license notice. The interface contains an illustration of the ellipsoid/geoid/terrain relationship.

### 01 — AOI geoid grid

1. Select an AOI polygon: `.geojson` / `.json`, `.gpkg`, a ZIP shapefile, or **all shapefile component files together** (`.shp`, `.shx`, `.dbf`, `.prj`, with optional `.cpg`). A `.shp` file alone is insufficient for reliable reading and CRS identification.
2. Supply the output pixel size. For a projected metre-based output this is in metres (e.g., `30` = 30 m).
3. The application detects the AOI input CRS from the geospatial file. If the AOI is already in an appropriate projected metre CRS it uses that by default; otherwise it estimates a local UTM CRS. You may override the **output** CRS with a projected EPSG code.
4. Select RAF20, EGM96, EGM2008 or a custom separation raster and click **Run conversion**.
5. Inspect the separation map with colorbar, contours and coordinate axes, then download the results ZIP. Areas outside the AOI are NoData.

### 02 — Elevation raster conversion

1. Supply a single-band elevation `.tif` / `.tiff`. For files within the browser's upload limit (400 MB), use the file picker. For larger rasters, enter the **absolute local file path** in the alternative field; use one input method, not both. Local-path access is appropriate **only on a trusted local installation**.
2. Select the model used to calculate separation. Indicate both the **source** and **target** vertical references; do not assume the original DEM is ellipsoidal or orthometric without checking metadata.
3. Run conversion. The resulting GeoTIFF retains the original raster geometry/CRS and NoData mask. The ZIP contains the converted raster, relevant separation raster(s), and metadata.
4. Review raster previews: color shading, contour labels, coordinate grid and X/Y axis values according to the raster CRS; previews also display elevation/separation range and raster dimensions. The PNG preview does **not** replace the full-resolution GeoTIFF.

### 03 — Coordinate points and CSV

- **Manual points:** choose **Enter coordinates** and enter one point per line as `x,y` or `x,y,z`. The application returns `N`, and computes a converted elevation when a valid `z` is supplied.
- **CSV:** choose **Import CSV file**, select the CSV, and specify X, Y and optional Z column names. The output keeps all original columns and adds `geoid_N_m` and, when an input elevation exists, `z_converted_m`.
- Set the input horizontal CRS (for example `EPSG:4326` for longitude/latitude, noting **X=longitude, Y=latitude**). Select the appropriate geoid and source/target height references. Results include a table preview (up to 50 rows) and a downloadable CSV ZIP.

### 05 — DEM downloads

1. Upload/select the AOI boundary as above and choose **Copernicus DEM GLO-30**, **SRTM1**, or **IGN LiDAR HD DSM**.
2. For global DEMs, adjust the geographic buffer (degrees). For IGN, configure the target raster resolution and tile-selection buffer (metres).
3. Check the dataset's **native vertical reference** before choosing an optional conversion: Copernicus GLO-30 typically uses EGM2008; SRTM typically uses EGM96; mainland-France IGN LiDAR HD products generally use NGF-IGN69, but the actual product metadata is authoritative.
4. Choose **Keep source heights** or **Also produce ellipsoidal heights**. In the latter case the ZIP also contains the transformed DEM and separation raster(s).
5. Download the resulting ZIP after processing and inspect the preview maps where available.

**Important:** Remote DEM download depends on internet access, service availability, coverage and provider API conventions. The IGN tile-index service has previously returned HTTP 400 errors; automatic IGN retrieval is **not guaranteed** by this release. Use the provider's official download portal if required. Model grids and external service access may also require network connectivity.

### 06 — GPS Time

Select the input format: GPS seconds since **1980-01-06**, GPS week and seconds-of-week, UTC ISO 8601, Unix timestamp seconds, or the legacy `GPS seconds − 1,000,000,000` convention. Click **Convert time** to display UTC, Unix, GPS seconds, GPS week, seconds of week, GPS–UTC offset, and the legacy value. The application includes a historical leap-second table up to the 2017 update. **Verify leap-second-table currency for future GNSS data**, and note that a UTC `23:59:60` leap-second instant cannot be represented directly using JavaScript Date.

### Advanced / legacy

The `advanced_legacy/` directory retains the former Reference DEM Utility with notebook and supporting scripts, including source acquisition, reprojecting and DEM preparation. The active browser interface is launched separately via `geoid_web.py`.

## Installation and launch

### Recommended: Micromamba on Windows

Open PowerShell in the extracted application folder (the folder containing `geoid_web.py`). Create the environment once:

```powershell
micromamba create -n geoid_tool -c conda-forge python=3.12 numpy scipy rasterio geopandas pyproj requests matplotlib pandas shapely affine -y
```

On subsequent launches:

```powershell
micromamba activate geoid_tool
python geoid_web.py
```

Then open **http://127.0.0.1:8765/** in a browser and **leave PowerShell running** while working. Alternatively, run `START_WINDOWS.bat` if it recognizes your configured Python environment. To stop, press `Ctrl+C` in the server terminal.

If Python and the required native geospatial dependencies are already installed, install any remaining requirements with `python -m pip install -r requirements.txt`. Linux/macOS installations may use `START_LINUX_MAC.sh` after configuring the environment. The application is designed for a local Python server, **not direct double-click execution of `geoid_interface.html`**.

### Troubleshooting

| Symptom | What to check |
| --- | --- |
| “Cannot connect to Python processing server” | Start `python geoid_web.py`, check the terminal for errors, keep it open, and load `http://127.0.0.1:8765/`; close older instances on port 8765. |
| `python` or `py` is not recognized | Activate the `geoid_tool` Micromamba environment before launching. |
| “Upload limit 400 MB” | Enter the local absolute GeoTIFF path in panel 02 instead of using browser upload. |
| Shapefile does not load | Include `.shp`, `.shx`, `.dbf` and `.prj` together or provide a ZIP; verify the CRS metadata. |
| Model grid not available | Confirm geographic coverage and that required PROJ model grids are installed/accessibly configured. |
| IGN service error | The upstream service or its query API may be unavailable; try the provider's official download portal. |

## Outputs and quality control

Processing outputs are delivered in a **results ZIP** with `metadata.json`; relevant raster workflows return GeoTIFFs and generated preview maps are displayed in the interface. Point/CSV workflows return CSV tables. Height-reference assumptions, coordinate systems, NoData coverage, source metadata and plausible known control points should be checked before scientific interpretation. Large rasters need adequate free disk space and memory even when browser uploading is bypassed.

## Source structure

```text
geodetic-elevation-data-toolkit/
  README.md                  # main user guide (this file)
  README_GEOID.md            # additional copy of the user guide
  geoid_interface.html       # local browser UI and GPS Time panel
  geoid_web.py               # local HTTP server and result previews
  geoid_engine.py            # height and separation processing
  vertical_reference.py      # model/grid transformations
  global_dem_downloader.py   # Copernicus and SRTM source handling
  ign_lidarhd_downloader.py  # IGN LiDAR HD source handling
  reference_dem_interface.py # original reference DEM interface
  data/RAF20.tac             # bundled regional model data
  assets/                    # illustrations and logos
  advanced_legacy/           # preserved original notebook workflow
  START_WINDOWS.bat
  START_LINUX_MAC.sh
  requirements.txt
  LICENSE                    # CeCILL-B
  NOTICE.md                  # attribution and third-party terms
  CITATION.cff               # software metadata
  CHANGELOG.md
  release_smoke_test.py       # offline RAF20 regression check
  RELEASE_NOTES_v5.0.0.md   # release documentation
```

## License and attribution

The **original toolkit source code is licensed under CeCILL-B**; see [`LICENSE`](LICENSE). The license does not automatically cover downloaded or bundled third-party materials, including IGN/EGM datasets, other data, dependencies, logos or illustrations. Review [`NOTICE.md`](NOTICE.md) and the respective upstream rights before redistribution. Affiliation/branding does not indicate institutional endorsement.

## Technical references

- [IGN geodesy / RAF20](https://geodesie.ign.fr/)
- [PROJ vertical grid shift](https://proj.org/en/stable/operations/transformations/vgridshift.html)
- [EPSG geodetic registry](https://epsg.org/)
- [Copernicus DEM](https://dataspace.copernicus.eu/explore-data/data-collections/copernicus-contributing-missions/copernicus-dem)
- [NASA SRTM](https://www.earthdata.nasa.gov/data/instruments/srtm)
- [IGN Géoplateforme](https://cartes.gouv.fr/)
- [Micromamba user guide](https://mamba.readthedocs.io/en/latest/user_guide/micromamba.html)
- [IERS Earth orientation/time references](https://www.iers.org/IERS/EN/DataProducts/EarthOrientationData/eop.html)
