# Reference DEM Utility

**Version 1.0.1**

A notebook-based research utility for preparing one reference DEM from an AOI.

It supports:

- automatic download of **Copernicus DEM GLO-30**;
- automatic download of **SRTM1 30 m**;
- automatic download and aggregation of **IGN LiDAR HD MNS/DSM** in mainland France;
- preparation of an **existing DEM**;
- output-resolution control;
- horizontal CRS reprojection;
- optional **geoid ↔ ellipsoid** conversion;
- saving and visualizing the geoid/quasi-geoid separation model;
- compact QC figures, statistics, configuration and logs.

The software produces **one final DEM**.

---

## 1. Quick start

Download or clone the repository and keep the files together.

Open:

```text
Reference_DEM_Utility.ipynb
```

Then click:

```text
▶ Start Reference DEM Utility
```

The startup cell checks for required Python packages and installs only packages
that are missing.

Required Python packages:

```text
ipywidgets
geopandas
rasterio
pyproj
matplotlib
numpy
pandas
shapely
affine
scipy
```

A conventional installation is also possible:

```bash
python -m pip install -r requirements.txt
```

Internet access is required when a missing Python package, DEM tile, or PROJ
vertical grid must be downloaded.

---

## 2. Workflow

```text
AOI / country
      ↓
Select DEM source
      ↓
Choose DEM resolution
      ↓
Choose one final horizontal CRS
      ↓
Optional vertical conversion
      ↓
ONE FINAL DEM
      ↓
QC + geoid-model map + configuration + log
```

---

## 3. DEM sources

### Copernicus DEM GLO-30

Default output resolution:

```text
30 m
```

Source horizontal reference:

```text
WGS 84 geographic
EPSG:4326
```

Official Copernicus GLO-30 vertical reference:

```text
EGM2008
EPSG:3855
```

Reference:

- Copernicus DEM Product Handbook:
  https://dataspace.copernicus.eu/sites/default/files/media/files/2024-06/geo1988-copernicusdem-spe-002_producthandbook_i5.0.pdf
- Copernicus Data Space:
  https://dataspace.copernicus.eu/explore-data/data-collections/copernicus-contributing-missions/collections-description/COP-DEM

### SRTM1

Default output resolution:

```text
30 m
```

Source horizontal reference:

```text
WGS 84 geographic
EPSG:4326
```

Official vertical reference:

```text
EGM96
```

Reference:

- USGS SRTM 1 Arc-Second Global:
  https://www.usgs.gov/centers/eros/science/usgs-eros-archive-digital-elevation-shuttle-radar-topography-mission-srtm-1

### IGN LiDAR HD

Available when:

```text
Country / region = France — mainland
```

Native MNS/DSM resolution:

```text
0.5 m
```

Default prepared resolution:

```text
1 m
```

Horizontal source CRS:

```text
RGF93 / Lambert-93
EPSG:2154
```

The supplied France vertical workflow uses the RAF20 conversion surface.

IGN references:

- RAF20 conversion grids:
  https://geodesie.ign.fr/grilles-de-conversion
- IGN geodetic FAQ:
  https://geodesie.ign.fr/faq
- RAF20 technical documentation:
  https://geodesie.ign.fr/files/geodesie/2024-12/RAF20.pdf

### Existing DEM

No elevation dataset is downloaded.

The user supplies a georeferenced raster and may:

- change output resolution;
- preserve its horizontal CRS;
- convert to WGS 84 / EPSG:4326;
- use an automatically selected local projected CRS;
- enter a custom CRS;
- keep the current heights;
- convert geoid → ellipsoid;
- convert ellipsoid → geoid.

---

## 4. Output resolution

One control is used:

```text
DEM resolution (m)
```

Defaults:

| Source | Default | Native / nominal |
|---|---:|---:|
| Copernicus GLO-30 | 30 m | ~30 m |
| SRTM1 | 30 m | ~30 m |
| IGN LiDAR HD | 1 m | 0.5 m |
| Existing DEM | user-defined | read from source |

If an output grid is finer than the source resolution, the software reports a
warning. A finer grid does **not** create additional terrain information.

---

## 5. Final horizontal CRS

The software writes one final horizontal CRS.

Options:

```text
Keep source CRS
WGS 84 geographic — EPSG:4326
Local projected CRS — automatic
Custom CRS
```

### Automatic local projected CRS

For ordinary latitudes the program automatically chooses the local
WGS 84 / UTM zone from the AOI.

Polar projected CRS are used outside the standard UTM latitude range.

### Custom CRS

Any CRS accepted by PROJ/rasterio can be entered, for example:

```text
EPSG:32631
EPSG:32632
EPSG:4326
EPSG:3031
```

Horizontal reprojection is independent from vertical height conversion.

---

## 6. Vertical conversion

Vertical conversion is optional.

### Basic height relationship

```text
h = H + N
H = h - N
```

where:

```text
h = ellipsoidal height
H = geoid / physical height
N = geoid or quasi-geoid separation
```

The software always applies a **spatially varying N raster**. It does not use a
single constant vertical offset.

### Downloaded DEMs

The interface contains one checkbox:

```text
Convert geoid heights to ellipsoidal heights
```

Only after checking it does the geoid-model selector appear.

#### France mode

When:

```text
Country / region = France — mainland
```

the default model is:

```text
RAF20
```

The user may change it to:

```text
EGM96
EGM2008
Custom N raster
```

This default is a workflow setting and is intentionally editable.

**Important metadata note:** untouched native SRTM data are documented as
EGM96 and untouched native Copernicus GLO-30 data as EGM2008. Users should make
the model selection consistent with the vertical reference of the DEM they
intend to process.

#### Other / global mode

Defaults are source-aware:

```text
SRTM       → EGM96
Copernicus → EGM2008
```

The user can still change between EGM96, EGM2008 and a custom N raster.

### Existing DEM

The interface shows:

```text
No vertical conversion
Geoid → ellipsoid
Ellipsoid → geoid
```

When a conversion is selected, the geoid-model selector appears.

France default:

```text
RAF20
```

Other/global default:

```text
EGM96
```

Available models:

```text
RAF20       [France]
EGM96
EGM2008
Custom N raster
```

---

## 7. RAF20 — mainland France

The repository includes:

```text
data/RAF20.tac
```

RAF20 is interpolated spatially to the working DEM grid.

The conversion is:

```text
geoid / physical → ellipsoid:
h = H + N

ellipsoid → geoid / physical:
H = h - N
```

The implementation follows the supplied RAF20 workflow and does not replace
the grid by an average or constant correction.

IGN describes RAF20 as the mainland-France altitude-conversion surface linking
RGF93 ellipsoidal heights and NGF-IGN69.

---

## 8. EGM96 and EGM2008

Global vertical models use **PROJ through pyproj**.

The utility requests the appropriate PROJ vertical transformation and attempts
to download missing open-license grids into:

```text
vertical_grids/
```

If PROJ cannot provide the transformation and NASA Ames Stereo Pipeline
`dem_geoid` is installed, `dem_geoid` is used as a fallback.

ASP documentation:

- https://stereopipeline.readthedocs.io/en/latest/tools/dem_geoid.html
- https://stereopipeline.readthedocs.io/en/latest/next_steps.html

ASP supports EGM96 and EGM2008 and provides `--reverse-adjustment` for
geoid-to-ellipsoid conversion.

---

## 9. Custom geoid / quasi-geoid model

For another national or local model, provide a georeferenced GeoTIFF whose
values are:

```text
N = h - H
```

in metres.

The custom raster may have another horizontal CRS. It is aligned automatically
to the DEM grid with bilinear interpolation before applying the vertical
conversion.

This makes the utility extensible outside France without hard-coding every
national geoid model.

---

## 10. Geoid-model output and map

When a vertical conversion is selected, this option appears:

```text
Save and show the geoid model used
```

It is enabled by default.

The aligned geoid-separation raster is saved under:

```text
vertical_models/
```

Example:

```text
vertical_models/N_raf20.tif
vertical_models/N_egm96.tif
vertical_models/N_egm2008.tif
```

The raster represents:

```text
N = h - H
```

in metres.

The notebook's **Geoid model** tab displays:

- a terrain-style color scale;
- labeled contour lines;
- AOI boundary;
- horizontal coordinates;
- colorbar in metres.

PNG and PDF versions are also saved under:

```text
qc/
```

---

## 11. SRTM / vertical-conversion validation

Version 1.0.0 adds explicit checks after:

```text
source DEM preparation
horizontal reprojection
geoid-model generation
final vertical conversion
```

If any stage contains no finite values, processing stops with a clear error.

An all-NoData result can therefore no longer be displayed as a successful blank
DEM.

For EGM96 / EGM2008, an invalid PROJ-generated model triggers the ASP
`dem_geoid` fallback when ASP is available.

---

## 12. Output structure

Typical project output:

```text
<Project>/
├── final/
│   └── Reference_DEM_....tif
│
├── vertical_models/
│   └── N_<model>.tif
│
├── vertical_grids/
│   └── downloaded PROJ grid files
│
├── cache/
│   └── downloaded/source DEM material
│
├── qc/
│   ├── final_reference_dem.png
│   ├── final_reference_dem.pdf
│   ├── geoid_model_<model>.png
│   ├── geoid_model_<model>.pdf
│   └── final_dem_qc.csv
│
├── logs/
│   └── reference_dem.log
│
└── reference_dem_config.json
```

The user-facing elevation result is always:

```text
ONE FINAL DEM
```

under `final/`.

---

## 13. Repository files

```text
Reference_DEM_Utility.ipynb
reference_dem_interface.py
vertical_reference.py
global_dem_downloader.py
ign_lidarhd_downloader.py
requirements.txt
README.md
CITATION.cff
assets/
    Geoid_concept.png
data/
    RAF20.tac
```

---

## 14. Reproducibility information

Every run writes:

```text
reference_dem_config.json
```

including:

- selected source;
- AOI;
- output resolution;
- final horizontal CRS;
- selected vertical-conversion option;
- selected geoid model;
- final vertical reference;
- final DEM path;
- validity/elevation information.

Detailed processing messages are stored in:

```text
logs/reference_dem.log
```

---

## 15. Citation

If this software is used in a scientific workflow, please cite the software
release and the relevant DEM/geodetic data providers.

A GitHub-compatible `CITATION.cff` file is included.

For Copernicus GLO-30, follow the official Copernicus DEM attribution and
licensing instructions.

---

## 16. Scope and limitations

- Vertical conversions are only meaningful when the selected geoid model
  corresponds to the intended height reference.
- RAF20 is intended for mainland France.
- A finer raster grid than the native source is resampling, not additional
  spatial information.
- Global EGM model/grid downloads require internet access if the required PROJ
  grids are not already installed.
- Automatic Python dependency installation requires permission to install into
  the active Python environment.
- The software does not silently accept an all-NoData DEM or geoid model.


---

## 17. Patch release 1.0.1

Fixed a startup/runtime bug in geoid-model plotting:

```text
NameError: name 'math' is not defined
```

The contour-level calculation uses Python's standard `math` module. Version
1.0.1 imports it explicitly. No processing logic, defaults, CRS behavior,
vertical-conversion behavior, or output structure was changed.
