
from __future__ import annotations

from contextlib import redirect_stdout, redirect_stderr
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import html
import json
import math
import shutil

import geopandas as gpd
import ipywidgets as widgets
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import rasterio
from IPython.display import display
from matplotlib.ticker import FuncFormatter, MaxNLocator
from pyproj import CRS
from pyproj.aoi import AreaOfInterest
from pyproj.database import query_utm_crs_info
from rasterio.enums import Resampling
from rasterio.warp import calculate_default_transform, reproject

import global_dem_downloader as global_dem
import ign_lidarhd_downloader as ign_lidar
from vertical_reference import build_n_raster, convert_between_models


VERSION = "1.0.1"
MODULE_DIR = Path(__file__).resolve().parent
RAF20_PATH = MODULE_DIR / "data" / "RAF20.tac"
CONCEPT_IMAGE = MODULE_DIR / "assets" / "Geoid_concept.png"


@dataclass
class Settings:
    aoi_path: Path
    output_dir: Path
    region: str
    source: str
    resolution_m: float

    existing_dem: Path | None = None

    global_buffer_deg: float = 0.05
    ign_buffer_m: float = 1000.0
    ign_workers: int = 2

    final_crs_mode: str = "source"
    custom_crs: str = ""
    resampling: str = "bilinear"

    # Downloaded DEM: one simple optional vertical conversion.
    convert_downloaded_to_ellipsoid: bool = False
    downloaded_geoid_model: str = "raf20"
    downloaded_custom_n_raster: Path | None = None

    # Existing DEM.
    existing_vertical_conversion: str = "none"
    existing_geoid_model: str = "raf20"
    existing_custom_n_raster: Path | None = None

    # Appears only when vertical conversion is active.
    save_show_geoid_model: bool = True


# =====================================================================
# AOI / CRS
# =====================================================================

def read_aoi(path):
    path = Path(path).expanduser()

    if not path.is_file():
        raise FileNotFoundError(f"AOI vector not found:\n{path}")

    aoi = gpd.read_file(path)

    if aoi.empty:
        raise ValueError("AOI vector is empty.")

    if aoi.crs is None:
        raise ValueError("AOI has no CRS. Define its CRS first.")

    keep = aoi.geometry.notna() & ~aoi.geometry.is_empty
    aoi = aoi.loc[keep].copy()

    if aoi.empty:
        raise ValueError("AOI contains no valid geometry.")

    invalid = ~aoi.geometry.is_valid
    if invalid.any():
        aoi.loc[invalid, "geometry"] = (
            aoi.loc[invalid, "geometry"].buffer(0)
        )

    return aoi


def aoi_center(aoi):
    wgs = aoi.to_crs("EPSG:4326")
    minx, miny, maxx, maxy = map(float, wgs.total_bounds)
    return (minx + maxx) / 2.0, (miny + maxy) / 2.0


def auto_local_crs(aoi):
    lon, lat = aoi_center(aoi)

    if lat >= 84:
        return CRS.from_epsg(3413)

    if lat <= -80:
        return CRS.from_epsg(3031)

    infos = query_utm_crs_info(
        datum_name="WGS 84",
        area_of_interest=AreaOfInterest(
            west_lon_degree=lon,
            south_lat_degree=lat,
            east_lon_degree=lon,
            north_lat_degree=lat,
        ),
    )

    if not infos:
        raise RuntimeError("Could not determine a local projected CRS.")

    return CRS.from_epsg(int(infos[0].code))


def final_crs(settings, aoi, source_crs):
    if settings.final_crs_mode == "source":
        return CRS.from_user_input(source_crs)

    if settings.final_crs_mode == "wgs84":
        return CRS.from_epsg(4326)

    if settings.final_crs_mode == "local":
        return auto_local_crs(aoi)

    if settings.final_crs_mode == "custom":
        value = settings.custom_crs.strip()

        if not value:
            raise ValueError(
                "Enter the target CRS, for example EPSG:32632."
            )

        return CRS.from_user_input(value)

    raise ValueError(
        f"Unknown final CRS mode: {settings.final_crs_mode}"
    )


# =====================================================================
# Raster helpers and validation
# =====================================================================

def resampling_enum(name):
    try:
        return Resampling[str(name)]
    except KeyError as exc:
        raise ValueError(f"Unsupported resampling: {name}") from exc


def output_profile(src, crs, transform, width, height):
    profile = src.profile.copy()
    profile.pop("blockxsize", None)
    profile.pop("blockysize", None)

    tiled = width >= 256 and height >= 256

    profile.update(
        driver="GTiff",
        crs=crs,
        transform=transform,
        width=width,
        height=height,
        count=1,
        dtype="float32",
        nodata=np.nan,
        compress="deflate",
        tiled=tiled,
        BIGTIFF="IF_SAFER",
    )

    if tiled:
        profile.update(
            blockxsize=256,
            blockysize=256,
        )

    return profile


def raster_validity(path, label="raster"):
    """
    Return finite-value statistics and fail clearly on an empty/all-NoData raster.
    """
    path = Path(path)

    with rasterio.open(path) as src:
        data = src.read(1, masked=True)
        values = np.asarray(data.compressed(), dtype=np.float64)

    values = values[np.isfinite(values)]

    if values.size == 0:
        raise RuntimeError(
            f"{label} contains no finite elevation/model values: {path}"
        )

    return {
        "count": int(values.size),
        "min": float(np.min(values)),
        "max": float(np.max(values)),
        "mean": float(np.mean(values)),
    }


def prepare_horizontal(
    src_path,
    dst_path,
    dst_crs,
    resolution_m,
    resampling,
):
    src_path = Path(src_path)
    dst_path = Path(dst_path)
    dst_path.parent.mkdir(parents=True, exist_ok=True)

    dst_crs = CRS.from_user_input(dst_crs)

    with rasterio.open(src_path) as src:
        if src.crs is None:
            raise ValueError("Source DEM has no horizontal CRS.")

        kwargs = {}

        # Exact metre resolution only applies to projected CRS.
        if dst_crs.is_projected:
            kwargs["resolution"] = float(resolution_m)

        transform, width, height = calculate_default_transform(
            src.crs,
            dst_crs,
            src.width,
            src.height,
            *src.bounds,
            **kwargs,
        )

        profile = output_profile(
            src,
            dst_crs,
            transform,
            width,
            height,
        )

        with rasterio.open(dst_path, "w", **profile) as dst:
            reproject(
                source=rasterio.band(src, 1),
                destination=rasterio.band(dst, 1),
                src_transform=src.transform,
                src_crs=src.crs,
                src_nodata=src.nodata,
                dst_transform=transform,
                dst_crs=dst_crs,
                dst_nodata=np.nan,
                resampling=resampling_enum(resampling),
            )

    raster_validity(
        dst_path,
        label="Horizontally prepared DEM",
    )

    return dst_path


def raster_stats(path):
    path = Path(path)
    valid = raster_validity(path, label="Final DEM")

    with rasterio.open(path) as src:
        total = src.width * src.height

        return {
            "Path": str(path),
            "CRS": src.crs.to_string() if src.crs else "",
            "Width": int(src.width),
            "Height": int(src.height),
            "Resolution X": abs(float(src.transform.a)),
            "Resolution Y": abs(float(src.transform.e)),
            "Valid pixels": valid["count"],
            "Valid (%)": 100.0 * valid["count"] / total if total else 0.0,
            "Min elevation (m)": valid["min"],
            "Max elevation (m)": valid["max"],
            "Mean elevation (m)": valid["mean"],
        }


def preview_data(path, max_size=1400):
    with rasterio.open(path) as src:
        scale = max(
            src.width / max_size,
            src.height / max_size,
            1.0,
        )

        width = max(1, int(src.width / scale))
        height = max(1, int(src.height / scale))

        data = src.read(
            1,
            out_shape=(height, width),
            masked=True,
        )

        return data, src.bounds, src.crs


def format_axes(ax, crs):
    if crs.is_geographic:
        ax.set_xlabel("Longitude")
        ax.set_ylabel("Latitude")
        formatter = FuncFormatter(
            lambda value, pos: f"{value:.4f}"
        )
    else:
        ax.set_xlabel("Easting (m)")
        ax.set_ylabel("Northing (m)")
        formatter = FuncFormatter(
            lambda value, pos: f"{value:,.0f}"
        )

    ax.xaxis.set_major_locator(MaxNLocator(nbins=6))
    ax.yaxis.set_major_locator(MaxNLocator(nbins=6))
    ax.xaxis.set_major_formatter(formatter)
    ax.yaxis.set_major_formatter(formatter)
    ax.tick_params(axis="x", labelrotation=25)


def _nice_contour_interval(data_range):
    """
    Choose a readable 1/2/5-style contour interval targeting ~8 contours.
    """
    if not np.isfinite(data_range) or data_range <= 0:
        return None

    raw = data_range / 8.0
    magnitude = 10.0 ** np.floor(np.log10(raw))
    normalized = raw / magnitude

    if normalized <= 1:
        nice = 1.0
    elif normalized <= 2:
        nice = 2.0
    elif normalized <= 5:
        nice = 5.0
    else:
        nice = 10.0

    return nice * magnitude


def plot_raster(
    path,
    aoi,
    title,
    label,
    output_base,
    *,
    cmap="terrain",
    add_contours=False,
):
    """
    Plot a DEM/model with a vertical colorbar.

    The requested publication style uses matplotlib's 'terrain' colormap:
    dark blue -> cyan/green -> yellow/brown -> white.
    """
    path = Path(path)
    raster_validity(path, label=title)

    data, bounds, crs = preview_data(path)
    aoi_plot = aoi.to_crs(crs)

    fig, ax = plt.subplots(
        figsize=(9.5, 7.0)
    )

    cmap_obj = plt.get_cmap(cmap).copy()
    cmap_obj.set_bad(alpha=0)

    image = ax.imshow(
        data,
        extent=(
            bounds.left,
            bounds.right,
            bounds.bottom,
            bounds.top,
        ),
        origin="upper",
        cmap=cmap_obj,
    )

    if add_contours:
        filled = np.asarray(
            np.ma.filled(data, np.nan),
            dtype=np.float64,
        )

        finite = filled[np.isfinite(filled)]

        if finite.size:
            zmin = float(np.min(finite))
            zmax = float(np.max(finite))
            interval = _nice_contour_interval(zmax - zmin)

            if interval is not None:
                first = math.floor(zmin / interval) * interval
                last = math.ceil(zmax / interval) * interval
                levels = np.arange(
                    first,
                    last + 0.5 * interval,
                    interval,
                )

                # Avoid a meaningless one-level contour.
                levels = levels[
                    (levels >= zmin)
                    & (levels <= zmax)
                ]

                if levels.size >= 2:
                    xs = np.linspace(
                        bounds.left,
                        bounds.right,
                        filled.shape[1],
                    )

                    # imshow origin="upper": first row corresponds to top.
                    ys = np.linspace(
                        bounds.top,
                        bounds.bottom,
                        filled.shape[0],
                    )

                    contours = ax.contour(
                        xs,
                        ys,
                        filled,
                        levels=levels,
                        linewidths=0.65,
                        colors="black",
                        alpha=0.70,
                    )

                    ax.clabel(
                        contours,
                        inline=True,
                        fontsize=7,
                        fmt=lambda value: f"{value:g}",
                    )

    aoi_plot.boundary.plot(
        ax=ax,
        linewidth=1.2,
    )

    colorbar = fig.colorbar(
        image,
        ax=ax,
        shrink=0.86,
        pad=0.02,
    )

    colorbar.set_label(label)

    ax.set_title(title)
    format_axes(ax, crs)
    ax.set_aspect("equal")
    fig.tight_layout()

    output_base = Path(output_base)
    output_base.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    png = output_base.with_suffix(".png")
    pdf = output_base.with_suffix(".pdf")

    fig.savefig(
        png,
        dpi=200,
        bbox_inches="tight",
    )

    fig.savefig(
        pdf,
        dpi=300,
        bbox_inches="tight",
    )

    plt.close(fig)

    return {
        "png": png,
        "pdf": pdf,
    }


# =====================================================================
# Source DEM
# =====================================================================

def prepare_source(settings):
    cache = settings.output_dir / "cache"
    cache.mkdir(parents=True, exist_ok=True)

    if settings.source == "copernicus":
        path = cache / "Copernicus_GLO30_WGS84.tif"

        global_dem.download_copernicus(
            aoi_path=settings.aoi_path,
            out_tif=path,
            buffer_deg=settings.global_buffer_deg,
            plot=False,
        )

        raster_validity(
            path,
            label="Downloaded Copernicus DEM",
        )

        return {
            "key": "copernicus",
            "label": "Copernicus DEM GLO-30",
            "path": path,
            "native_resolution_m": 30.0,
            "native_vertical": "EGM2008",
        }

    if settings.source == "srtm":
        path = cache / "SRTM1_30m_WGS84.tif"

        global_dem.download_srtm(
            aoi_path=settings.aoi_path,
            out_tif=path,
            buffer_deg=settings.global_buffer_deg,
            plot=False,
        )

        raster_validity(
            path,
            label="Downloaded SRTM DEM",
        )

        return {
            "key": "srtm",
            "label": "SRTM1 30 m",
            "path": path,
            "native_resolution_m": 30.0,
            "native_vertical": "EGM96",
        }

    if settings.source == "ign":
        if settings.region != "france":
            raise ValueError(
                "IGN LiDAR HD is available here only for mainland France."
            )

        outputs = ign_lidar.download_ign_lidarhd_dsm(
            aoi_path=settings.aoi_path,
            out_dir=cache / "IGN_LiDAR_HD",
            target_res=settings.resolution_m,
            download_buffer=True,
            buffer_distance_m=settings.ign_buffer_m,
            n_workers=settings.ign_workers,
            aggregation_fun="mean",
            export_to_wgs84=False,
            plot_results=False,
        )

        path = Path(outputs["bbox_epsg2154"])

        raster_validity(
            path,
            label="Prepared IGN LiDAR HD DEM",
        )

        return {
            "key": "ign",
            "label": "IGN LiDAR HD MNS/DSM",
            "path": path,
            "native_resolution_m": 0.5,
            "native_vertical": "NGF-IGN69 / RAF20",
        }

    if settings.source == "existing":
        if settings.existing_dem is None:
            raise ValueError("Select the existing DEM.")

        path = Path(settings.existing_dem).expanduser()

        if not path.is_file():
            raise FileNotFoundError(
                f"Existing DEM not found:\n{path}"
            )

        with rasterio.open(path) as src:
            if src.crs is None:
                raise ValueError(
                    "Existing DEM has no horizontal CRS."
                )

        raster_validity(
            path,
            label="Existing DEM",
        )

        return {
            "key": "existing",
            "label": "Existing DEM",
            "path": path,
            "native_resolution_m": None,
            "native_vertical": "User-defined",
        }

    raise ValueError(
        f"Unsupported source: {settings.source}"
    )


# =====================================================================
# Geoid-model choices
# =====================================================================

def default_downloaded_geoid_model(region, source):
    """
    Default vertical-conversion model used by the interface.

    User-requested workflow:
    - France: RAF20 for all downloaded DEM sources, but editable.
    - Other/global:
        SRTM -> EGM96
        Copernicus -> EGM2008
    """
    if region == "france":
        return "raf20"

    if source == "srtm":
        return "egm96"

    if source == "copernicus":
        return "egm2008"

    return "egm96"


def geoid_label(model):
    labels = {
        "raf20": "RAF20 — mainland France",
        "egm96": "EGM96 — global",
        "egm2008": "EGM2008 — global",
        "custom": "Custom N raster",
    }

    return labels.get(model, model)


def downloaded_conversion(settings, source_info):
    if not settings.convert_downloaded_to_ellipsoid:
        return {
            "apply": False,
            "model": None,
            "source_model": None,
            "target_model": None,
            "final_vertical_label": (
                f"Source heights preserved ({source_info['native_vertical']})"
            ),
        }

    model = settings.downloaded_geoid_model

    return {
        "apply": True,
        "model": model,
        "source_model": model,
        "target_model": "ellipsoid",
        "final_vertical_label": "Ellipsoidal height",
    }


def existing_conversion(settings):
    mode = settings.existing_vertical_conversion

    if mode == "none":
        return {
            "apply": False,
            "model": None,
            "source_model": None,
            "target_model": None,
            "final_vertical_label": "Existing heights preserved",
        }

    model = settings.existing_geoid_model

    if mode == "geoid_to_ellipsoid":
        return {
            "apply": True,
            "model": model,
            "source_model": model,
            "target_model": "ellipsoid",
            "final_vertical_label": "Ellipsoidal height",
        }

    if mode == "ellipsoid_to_geoid":
        return {
            "apply": True,
            "model": model,
            "source_model": "ellipsoid",
            "target_model": model,
            "final_vertical_label": geoid_label(model),
        }

    raise ValueError(
        f"Unknown existing DEM vertical conversion: {mode}"
    )


# =====================================================================
# Main workflow
# =====================================================================

def prepare_reference_dem(settings, progress_callback=None):
    settings.output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    temp_dir = settings.output_dir / "temp"
    final_dir = settings.output_dir / "final"
    vertical_dir = settings.output_dir / "vertical_models"
    grid_cache = settings.output_dir / "vertical_grids"
    qc_dir = settings.output_dir / "qc"
    log_dir = settings.output_dir / "logs"

    for folder in (
        temp_dir,
        final_dir,
        vertical_dir,
        grid_cache,
        qc_dir,
        log_dir,
    ):
        folder.mkdir(
            parents=True,
            exist_ok=True,
        )

    log_path = log_dir / "reference_dem.log"

    def progress(value, text):
        if progress_callback:
            progress_callback(
                int(value),
                text,
            )

    progress(
        4,
        "Reading AOI",
    )

    aoi = read_aoi(
        settings.aoi_path
    )

    with log_path.open(
        "w",
        encoding="utf-8",
    ) as log:
        with redirect_stdout(log), redirect_stderr(log):
            print("=" * 72)
            print("REFERENCE DEM UTILITY")
            print("=" * 72)
            print("Version:", VERSION)
            print(
                "Time:",
                datetime.now().isoformat(
                    timespec="seconds"
                ),
            )
            print("Region:", settings.region)

            progress(
                14,
                "Preparing DEM source",
            )

            source_info = prepare_source(
                settings
            )

            source_path = Path(
                source_info["path"]
            )

            with rasterio.open(source_path) as src:
                source_crs = src.crs

            output_crs = final_crs(
                settings,
                aoi,
                source_crs,
            )

            progress(
                42,
                "Preparing final horizontal grid",
            )

            working_dem = (
                temp_dir
                / "horizontal_prepared.tif"
            )

            prepare_horizontal(
                source_path,
                working_dem,
                output_crs,
                settings.resolution_m,
                settings.resampling,
            )

            if source_info["key"] == "existing":
                vertical = existing_conversion(
                    settings
                )
                custom_n = (
                    settings.existing_custom_n_raster
                    if vertical["model"] == "custom"
                    else None
                )
            else:
                vertical = downloaded_conversion(
                    settings,
                    source_info,
                )
                custom_n = (
                    settings.downloaded_custom_n_raster
                    if vertical["model"] == "custom"
                    else None
                )

            n_path = None
            n_figure = None

            if vertical["apply"]:
                progress(
                    60,
                    "Preparing geoid separation model",
                )

                model = vertical["model"]

                n_path = (
                    vertical_dir / f"N_{model}.tif"
                    if settings.save_show_geoid_model
                    else temp_dir / f"N_{model}.tif"
                )

                build_n_raster(
                    template_dem=working_dem,
                    output_path=n_path,
                    model=model,
                    raf20_path=RAF20_PATH,
                    custom_n_raster=custom_n,
                    grid_cache_dir=grid_cache,
                )

                model_stats = raster_validity(
                    n_path,
                    label=f"{geoid_label(model)} separation model",
                )

                print(
                    f"Geoid model {model}: "
                    f"N min={model_stats['min']:.3f} m, "
                    f"max={model_stats['max']:.3f} m, "
                    f"mean={model_stats['mean']:.3f} m"
                )

                if settings.save_show_geoid_model:
                    n_figure = plot_raster(
                        n_path,
                        aoi,
                        f"{geoid_label(model)} — geoid separation",
                        "N = h − H (m)",
                        qc_dir / f"geoid_model_{model}",
                        cmap="terrain",
                        add_contours=True,
                    )

            progress(
                76,
                "Applying vertical conversion",
            )

            auth = output_crs.to_authority()

            crs_tag = (
                f"{auth[0]}{auth[1]}"
                if auth
                else "customCRS"
            )

            if vertical["apply"]:
                vertical_tag = (
                    "ellipsoidal"
                    if vertical["target_model"] == "ellipsoid"
                    else vertical["target_model"]
                )
            else:
                vertical_tag = "source_vertical"

            final_path = final_dir / (
                f"Reference_DEM_{source_info['key']}_"
                f"{settings.resolution_m:g}m_"
                f"{vertical_tag}_{crs_tag}.tif"
            )

            if vertical["apply"]:
                source_n = (
                    n_path
                    if vertical["source_model"] != "ellipsoid"
                    else None
                )

                target_n = (
                    n_path
                    if vertical["target_model"] != "ellipsoid"
                    else None
                )

                convert_between_models(
                    dem_path=working_dem,
                    output_path=final_path,
                    source_model=vertical["source_model"],
                    target_model=vertical["target_model"],
                    source_n_path=source_n,
                    target_n_path=target_n,
                )
            else:
                shutil.copy2(
                    working_dem,
                    final_path,
                )

            # Critical: never report success for an all-NoData final DEM.
            final_valid = raster_validity(
                final_path,
                label="Final reference DEM",
            )

            with rasterio.open(
                final_path,
                "r+",
            ) as dst:
                dst.update_tags(
                    REFERENCE_DEM_UTILITY_VERSION=VERSION,
                    SOURCE_DATASET=source_info["label"],
                    SOURCE_NATIVE_VERTICAL=source_info["native_vertical"],
                    FINAL_HORIZONTAL_CRS=output_crs.to_string(),
                    FINAL_VERTICAL_REFERENCE=vertical["final_vertical_label"],
                    GEOID_MODEL=(
                        geoid_label(vertical["model"])
                        if vertical["model"]
                        else "none"
                    ),
                )

            progress(
                88,
                "Creating final QC",
            )

            stats = raster_stats(
                final_path
            )

            pd.DataFrame(
                [stats]
            ).to_csv(
                qc_dir / "final_dem_qc.csv",
                index=False,
            )

            dem_figure = plot_raster(
                final_path,
                aoi,
                "Final reference DEM",
                "Elevation (m)",
                qc_dir / "final_reference_dem",
                cmap="terrain",
                add_contours=False,
            )

            warning = None
            native = source_info[
                "native_resolution_m"
            ]

            if (
                native is not None
                and settings.resolution_m < native
            ):
                warning = (
                    f"The requested {settings.resolution_m:g} m output grid "
                    f"is finer than the nominal/native {native:g} m source. "
                    "This is resampling only."
                )

            config = {
                "version": VERSION,
                "aoi": str(settings.aoi_path),
                "region": settings.region,
                "source": source_info["label"],
                "source_dem": str(source_path),
                "source_native_vertical_reference": (
                    source_info["native_vertical"]
                ),
                "requested_resolution_m": settings.resolution_m,
                "final_horizontal_crs": output_crs.to_string(),
                "vertical_conversion": (
                    settings.existing_vertical_conversion
                    if source_info["key"] == "existing"
                    else (
                        "geoid_to_ellipsoid"
                        if settings.convert_downloaded_to_ellipsoid
                        else "none"
                    )
                ),
                "geoid_model": vertical["model"],
                "geoid_model_label": (
                    geoid_label(vertical["model"])
                    if vertical["model"]
                    else None
                ),
                "geoid_model_raster": (
                    str(n_path)
                    if (
                        settings.save_show_geoid_model
                        and n_path
                    )
                    else None
                ),
                "final_vertical_reference": (
                    vertical["final_vertical_label"]
                ),
                "final_valid_pixels": (
                    final_valid["count"]
                ),
                "final_elevation_min_m": (
                    final_valid["min"]
                ),
                "final_elevation_max_m": (
                    final_valid["max"]
                ),
                "final_dem": str(final_path),
                "warning": warning,
            }

            config_path = (
                settings.output_dir
                / "reference_dem_config.json"
            )

            config_path.write_text(
                json.dumps(
                    config,
                    indent=2,
                ),
                encoding="utf-8",
            )

    working_dem.unlink(
        missing_ok=True
    )

    if (
        n_path is not None
        and not settings.save_show_geoid_model
        and n_path.parent == temp_dir
    ):
        n_path.unlink(
            missing_ok=True
        )

    progress(
        100,
        "Final DEM completed",
    )

    return {
        "source_info": source_info,
        "final_crs": output_crs,
        "final_vertical": (
            vertical["final_vertical_label"]
        ),
        "model": vertical["model"],
        "model_path": (
            n_path
            if settings.save_show_geoid_model
            else None
        ),
        "model_figure": n_figure,
        "final_dem": final_path,
        "stats": stats,
        "dem_figure": dem_figure,
        "warning": warning,
        "config_path": config_path,
        "log_path": log_path,
    }


# =====================================================================
# UI
# =====================================================================

def info_icon(text):
    return widgets.HTML(
        value=(
            "<span title='"
            + html.escape(
                text,
                quote=True,
            )
            + "' style='cursor:help;color:#1769aa;font-size:16px;'>"
            "ⓘ</span>"
        ),
        layout=widgets.Layout(
            width="24px"
        ),
    )


class ReferenceDEMUI:
    def __init__(self):
        style = {
            "description_width": "205px"
        }

        wide = widgets.Layout(
            width="830px"
        )

        self.region = widgets.Dropdown(
            options=[
                (
                    "France — mainland",
                    "france",
                ),
                (
                    "Other / global",
                    "global",
                ),
            ],
            value="france",
            description="Country / region:",
            style=style,
            layout=widgets.Layout(
                width="620px"
            ),
        )

        self.aoi = widgets.Text(
            description="AOI vector:",
            placeholder="/path/to/AOI.shp",
            style=style,
            layout=wide,
        )

        self.source = widgets.Dropdown(
            options=[],
            description="DEM source:",
            style=style,
            layout=widgets.Layout(
                width="660px"
            ),
        )

        self.existing_dem = widgets.Text(
            description="Existing DEM:",
            placeholder="/path/to/dem.tif",
            style=style,
            layout=wide,
        )

        self.resolution = widgets.FloatText(
            value=30.0,
            description="DEM resolution (m):",
            style=style,
        )

        self.global_buffer = widgets.FloatText(
            value=0.05,
            description="AOI buffer (deg):",
            style=style,
        )

        self.ign_buffer = widgets.FloatText(
            value=1000.0,
            description="Download buffer (m):",
            style=style,
        )

        self.ign_workers = widgets.IntText(
            value=2,
            description="Download workers:",
            style=style,
        )

        self.source_note = widgets.HTML()
        self.source_controls = widgets.VBox()
        self.source_advanced_box = widgets.VBox()

        self.source_advanced = widgets.Accordion(
            children=[
                self.source_advanced_box
            ]
        )

        self.source_advanced.set_title(
            0,
            "Advanced source settings",
        )

        # Horizontal CRS.
        self.final_crs_mode = widgets.Dropdown(
            options=[
                (
                    "Keep source CRS",
                    "source",
                ),
                (
                    "WGS 84 geographic — EPSG:4326",
                    "wgs84",
                ),
                (
                    "Local projected CRS — automatic",
                    "local",
                ),
                (
                    "Custom CRS",
                    "custom",
                ),
            ],
            value="source",
            description="Final CRS:",
            style=style,
            layout=widgets.Layout(
                width="700px"
            ),
        )

        self.custom_crs = widgets.Text(
            description="Target CRS:",
            placeholder=(
                "EPSG:32632 or another CRS accepted by PROJ/GDAL"
            ),
            style=style,
            layout=wide,
        )

        self.resampling = widgets.Dropdown(
            options=[
                (
                    "Bilinear",
                    "bilinear",
                ),
                (
                    "Nearest",
                    "nearest",
                ),
                (
                    "Cubic",
                    "cubic",
                ),
            ],
            value="bilinear",
            description="Resampling:",
            style=style,
        )

        self.crs_controls = widgets.VBox()

        # Downloaded DEM vertical conversion.
        self.convert_downloaded = widgets.Checkbox(
            value=False,
            description=(
                "Convert geoid heights to ellipsoidal heights"
            ),
            indent=False,
        )

        self.downloaded_model = widgets.Dropdown(
            options=[],
            description="Geoid model:",
            style=style,
            layout=widgets.Layout(
                width="720px"
            ),
        )

        self.downloaded_custom_n = widgets.Text(
            description="Custom N raster:",
            placeholder="/path/to/N_h_minus_H.tif",
            style=style,
            layout=wide,
        )

        # Existing DEM vertical conversion.
        self.existing_vertical = widgets.Dropdown(
            options=[
                (
                    "No vertical conversion",
                    "none",
                ),
                (
                    "Geoid → ellipsoid",
                    "geoid_to_ellipsoid",
                ),
                (
                    "Ellipsoid → geoid",
                    "ellipsoid_to_geoid",
                ),
            ],
            value="none",
            description="Vertical conversion:",
            style=style,
            layout=widgets.Layout(
                width="680px"
            ),
        )

        self.existing_model = widgets.Dropdown(
            options=[],
            description="Geoid model:",
            style=style,
            layout=widgets.Layout(
                width="720px"
            ),
        )

        self.existing_custom_n = widgets.Text(
            description="Custom N raster:",
            placeholder="/path/to/N_h_minus_H.tif",
            style=style,
            layout=wide,
        )

        self.save_show_model = widgets.Checkbox(
            value=True,
            description="Save and show the geoid model used",
            indent=False,
        )

        self.vertical_controls = widgets.VBox()

        self.concept_box = widgets.VBox()

        self.concept = widgets.Accordion(
            children=[
                self.concept_box
            ]
        )

        self.concept.set_title(
            0,
            "Height concept — optional",
        )

        self._build_concept()

        self.output_dir = widgets.Text(
            description="Output directory:",
            placeholder=(
                "Leave blank → <AOI>_Reference_DEM"
            ),
            style=style,
            layout=wide,
        )

        self.prepare = widgets.Button(
            description="▶ Prepare final DEM",
            button_style="success",
            icon="play",
            layout=widgets.Layout(
                width="285px",
                height="44px",
            ),
        )

        self.progress = widgets.IntProgress(
            min=0,
            max=100,
            value=0,
            description="Progress:",
            layout=widgets.Layout(
                width="790px"
            ),
        )

        self.progress_text = widgets.HTML()
        self.summary = widgets.HTML()

        self.qc_box = widgets.VBox()
        self.preview_box = widgets.VBox()
        self.model_box = widgets.VBox()
        self.log_box = widgets.VBox()

        self.tabs = widgets.Tab(
            children=[
                self.qc_box,
                self.preview_box,
                self.model_box,
                self.log_box,
            ]
        )

        for index, title in enumerate(
            [
                "Final DEM / QC",
                "DEM preview",
                "Geoid model",
                "Log",
            ]
        ):
            self.tabs.set_title(
                index,
                title,
            )

        self.region.observe(
            self._region_changed,
            names="value",
        )

        self.source.observe(
            self._source_changed,
            names="value",
        )

        self.final_crs_mode.observe(
            self._rebuild_crs,
            names="value",
        )

        self.convert_downloaded.observe(
            self._rebuild_vertical,
            names="value",
        )

        self.downloaded_model.observe(
            self._rebuild_vertical,
            names="value",
        )

        self.existing_vertical.observe(
            self._rebuild_vertical,
            names="value",
        )

        self.existing_model.observe(
            self._rebuild_vertical,
            names="value",
        )

        self.prepare.on_click(
            self._run
        )

        self._region_changed()
        self._rebuild_crs()

        self.root = widgets.VBox(
            [
                widgets.HTML(
                    value=(
                        "<h3 style='margin-bottom:4px;'>"
                        "Reference DEM Utility"
                        "</h3>"
                        "<div style='color:#666;margin-bottom:16px;'>"
                        "Choose the DEM, resolution, final CRS, and only "
                        "if needed apply a vertical conversion."
                        "</div>"
                    )
                ),

                widgets.HTML(
                    "<h4>1. Study area</h4>"
                ),
                self._row(
                    self.region,
                    (
                        "France makes RAF20 the default conversion model, "
                        "but the user can change it when conversion is enabled."
                    ),
                ),
                self._row(
                    self.aoi,
                    "AOI vector with a defined CRS.",
                ),

                widgets.HTML(
                    "<h4>2. DEM source</h4>"
                ),
                self._row(
                    self.source,
                    "Choose one DEM source.",
                ),
                self.source_note,
                self.source_controls,
                self.source_advanced,

                widgets.HTML(
                    "<h4>3. Final horizontal CRS</h4>"
                ),
                self.crs_controls,

                widgets.HTML(
                    "<h4>4. Vertical conversion — optional</h4>"
                ),
                self.vertical_controls,
                self.concept,

                widgets.HTML(
                    "<h4>5. Output</h4>"
                ),
                self._row(
                    self.output_dir,
                    (
                        "One final DEM is written to final/. If vertical "
                        "conversion is enabled, the geoid separation model "
                        "can also be saved and mapped."
                    ),
                ),

                widgets.HTML(
                    "<h4>6. Run</h4>"
                ),
                self.prepare,
                self.progress,
                self.progress_text,
                self.summary,
                self.tabs,
            ]
        )

    def _row(
        self,
        widget,
        text,
    ):
        return widgets.HBox(
            [
                widget,
                info_icon(
                    text
                ),
            ],
            layout=widgets.Layout(
                align_items="center",
                margin="3px 0",
            ),
        )

    def _build_concept(
        self,
    ):
        children = [
            widgets.HTML(
                value=(
                    "<div style='color:#555;line-height:1.55;'>"
                    "<b>Geoid → ellipsoid:</b> "
                    "<code>h = H + N</code><br>"
                    "<b>Ellipsoid → geoid:</b> "
                    "<code>H = h − N</code><br>"
                    "<b>N</b> is the spatial geoid/quasi-geoid separation."
                    "</div>"
                )
            )
        ]

        if CONCEPT_IMAGE.is_file():
            children.append(
                widgets.Image(
                    value=(
                        CONCEPT_IMAGE.read_bytes()
                    ),
                    format="png",
                    layout=widgets.Layout(
                        width="100%",
                        max_width="1050px",
                        height="auto",
                    ),
                )
            )

        self.concept_box.children = (
            tuple(
                children
            )
        )

    def _source_options(
        self,
    ):
        options = [
            (
                "Copernicus DEM GLO-30",
                "copernicus",
            ),
            (
                "SRTM1 30 m",
                "srtm",
            ),
        ]

        if (
            self.region.value
            == "france"
        ):
            options.append(
                (
                    "IGN LiDAR HD",
                    "ign",
                )
            )

        options.append(
            (
                "Existing DEM",
                "existing",
            )
        )

        return options

    def _geoid_options(
        self,
    ):
        options = []

        if (
            self.region.value
            == "france"
        ):
            options.append(
                (
                    "RAF20 — mainland France",
                    "raf20",
                )
            )

        options.extend(
            [
                (
                    "EGM96 — global",
                    "egm96",
                ),
                (
                    "EGM2008 — global",
                    "egm2008",
                ),
                (
                    "Custom N raster",
                    "custom",
                ),
            ]
        )

        return options

    def _recommended_download_model(
        self,
    ):
        return default_downloaded_geoid_model(
            self.region.value,
            self.source.value,
        )

    def _region_changed(
        self,
        change=None,
    ):
        current = (
            self.source.value
        )

        options = (
            self._source_options()
        )

        self.source.options = (
            options
        )

        allowed = {
            value
            for _, value in options
        }

        if current in allowed:
            self.source.value = (
                current
            )
        else:
            self.source.value = (
                options[0][1]
            )

        self._source_changed()

    def _source_changed(
        self,
        change=None,
    ):
        source = (
            self.source.value
        )

        if source == "ign":
            self.resolution.value = (
                1.0
            )
        elif source in {
            "copernicus",
            "srtm",
        }:
            self.resolution.value = (
                30.0
            )

        self._rebuild_source()
        self._rebuild_model_options()
        self._rebuild_vertical()

    def _rebuild_source(
        self,
    ):
        source = (
            self.source.value
        )

        if source == "copernicus":
            self.source_note.value = (
                "<div style='color:#555;margin:4px 0 8px 0;'>"
                "<b>Copernicus GLO-30</b> — nominal resolution "
                "<b>30 m</b>; horizontal WGS 84; native elevations "
                "are <b>EGM2008</b>."
                "</div>"
            )

            self.source_controls.children = (
                self._row(
                    self.resolution,
                    (
                        "Default 30 m. A finer grid is only resampling."
                    ),
                ),
            )

            self.source_advanced_box.children = (
                self._row(
                    self.global_buffer,
                    (
                        "AOI buffer used for global DEM tile selection."
                    ),
                ),
            )

        elif source == "srtm":
            self.source_note.value = (
                "<div style='color:#555;margin:4px 0 8px 0;'>"
                "<b>SRTM1</b> — nominal resolution <b>30 m</b>; "
                "horizontal WGS 84; native elevations are <b>EGM96</b>."
                "</div>"
            )

            self.source_controls.children = (
                self._row(
                    self.resolution,
                    (
                        "Default 30 m. A finer grid is only resampling."
                    ),
                ),
            )

            self.source_advanced_box.children = (
                self._row(
                    self.global_buffer,
                    (
                        "AOI buffer used for global DEM tile selection."
                    ),
                ),
            )

        elif source == "ign":
            self.source_note.value = (
                "<div style='color:#555;margin:4px 0 8px 0;'>"
                "<b>IGN LiDAR HD — mainland France</b><br>"
                "Native source resolution: <b>0.5 m</b>.<br>"
                "Default output resolution: <b>1 m</b>.<br>"
                "Horizontal source CRS: <b>EPSG:2154 "
                "RGF93 / Lambert-93</b>.<br>"
                "Native vertical reference: "
                "<b>NGF-IGN69 / RAF20</b>."
                "</div>"
            )

            self.source_controls.children = (
                self._row(
                    self.resolution,
                    (
                        "Default 1 m; native IGN MNS/DSM is 0.5 m."
                    ),
                ),
            )

            self.source_advanced_box.children = (
                self._row(
                    self.ign_buffer,
                    (
                        "Safety buffer around the AOI when selecting IGN tiles."
                    ),
                ),
                self._row(
                    self.ign_workers,
                    (
                        "Number of concurrent IGN downloads."
                    ),
                ),
            )

        else:
            self.source_note.value = (
                "<div style='color:#555;margin:4px 0 8px 0;'>"
                "<b>Existing DEM</b> — no DEM is downloaded. "
                "You can change resolution, final CRS, and optionally "
                "convert between geoid and ellipsoidal heights."
                "</div>"
            )

            self.source_controls.children = (
                self._row(
                    self.existing_dem,
                    (
                        "Existing georeferenced DEM with a "
                        "defined horizontal CRS."
                    ),
                ),
                self._row(
                    self.resolution,
                    (
                        "Final projected pixel size in metres."
                    ),
                ),
            )

            self.source_advanced_box.children = (
                widgets.HTML(
                    "<div style='color:#777;'>"
                    "No download-specific settings."
                    "</div>"
                ),
            )

    def _rebuild_crs(
        self,
        change=None,
    ):
        children = [
            self._row(
                self.final_crs_mode,
                (
                    "Choose one final horizontal CRS. "
                    "WGS 84 / EPSG:4326 is available for every source."
                ),
            )
        ]

        if (
            self.final_crs_mode.value
            == "custom"
        ):
            children.append(
                self._row(
                    self.custom_crs,
                    (
                        "Any CRS accepted by PROJ/GDAL, "
                        "for example EPSG:32632."
                    ),
                )
            )

        if (
            self.final_crs_mode.value
            == "local"
        ):
            children.append(
                widgets.HTML(
                    value=(
                        "<div style='color:#555;margin:4px 0;'>"
                        "Automatic local CRS uses WGS 84 / UTM "
                        "at ordinary latitudes and a polar projected "
                        "CRS near the poles."
                        "</div>"
                    )
                )
            )

        children.append(
            self._row(
                self.resampling,
                (
                    "Used only for horizontal reprojection/resampling."
                ),
            )
        )

        self.crs_controls.children = (
            tuple(
                children
            )
        )

    def _rebuild_model_options(
        self,
    ):
        options = (
            self._geoid_options()
        )

        # Downloaded model: reset to region/source default when source/region changes.
        self.downloaded_model.options = (
            options
        )

        recommended = (
            self._recommended_download_model()
        )

        allowed = {
            value
            for _, value in options
        }

        self.downloaded_model.value = (
            recommended
            if recommended in allowed
            else options[0][1]
        )

        # Existing DEM model: France defaults RAF20; global defaults EGM96.
        current = (
            self.existing_model.value
        )

        self.existing_model.options = (
            options
        )

        if current in allowed:
            self.existing_model.value = (
                current
            )
        else:
            self.existing_model.value = (
                "raf20"
                if (
                    self.region.value
                    == "france"
                )
                else "egm96"
            )

    def _rebuild_vertical(
        self,
        change=None,
    ):
        source = (
            self.source.value
        )

        children = []

        if source != "existing":
            children.append(
                self.convert_downloaded
            )

            if (
                self.convert_downloaded.value
            ):
                children.append(
                    self._row(
                        self.downloaded_model,
                        (
                            "France defaults to RAF20. "
                            "You may change to EGM96, EGM2008, "
                            "or a custom geoid-separation raster."
                        ),
                    )
                )

                if (
                    self.downloaded_model.value
                    == "custom"
                ):
                    children.append(
                        self._row(
                            self.downloaded_custom_n,
                            (
                                "GeoTIFF containing N = h − H in metres."
                            ),
                        )
                    )

                native = {
                    "srtm": "EGM96",
                    "copernicus": "EGM2008",
                    "ign": "NGF-IGN69 / RAF20",
                }[
                    source
                ]

                if (
                    self.region.value
                    == "france"
                ):
                    note = (
                        "<div style='padding:9px 12px;"
                        "border-left:4px solid #336699;"
                        "background:#f7f9fc;color:#555;margin-top:5px;'>"
                        "<b>France default:</b> RAF20. "
                        "The model is editable above.<br>"
                        "<b>Native source metadata:</b> "
                        + native
                        + "."
                        "</div>"
                    )
                else:
                    note = (
                        "<div style='padding:9px 12px;"
                        "border-left:4px solid #336699;"
                        "background:#f7f9fc;color:#555;margin-top:5px;'>"
                        "<b>Global default follows the source:</b> "
                        + native
                        + ". The model is editable above."
                        "</div>"
                    )

                children.append(
                    widgets.HTML(
                        value=note
                    )
                )

                children.append(
                    self.save_show_model
                )

        else:
            children.append(
                self._row(
                    self.existing_vertical,
                    (
                        "Choose no conversion, geoid → ellipsoid, "
                        "or ellipsoid → geoid."
                    ),
                )
            )

            if (
                self.existing_vertical.value
                != "none"
            ):
                children.append(
                    self._row(
                        self.existing_model,
                        (
                            "France defaults to RAF20; "
                            "other/global defaults to EGM96. "
                            "Change the model if required."
                        ),
                    )
                )

                if (
                    self.existing_model.value
                    == "custom"
                ):
                    children.append(
                        self._row(
                            self.existing_custom_n,
                            (
                                "GeoTIFF containing N = h − H in metres."
                            ),
                        )
                    )

                children.append(
                    self.save_show_model
                )

        conversion_active = (
            (
                source != "existing"
                and self.convert_downloaded.value
            )
            or (
                source == "existing"
                and (
                    self.existing_vertical.value
                    != "none"
                )
            )
        )

        if conversion_active:
            children.append(
                widgets.HTML(
                    value=(
                        "<div style='padding:9px 12px;"
                        "border-left:4px solid #d58b00;"
                        "background:#fffaf0;color:#555;margin-top:6px;'>"
                        "<b>Conversion:</b> geoid → ellipsoid uses "
                        "<code>h = H + N</code>; ellipsoid → geoid uses "
                        "<code>H = h − N</code>."
                        "</div>"
                    )
                )
            )

        self.vertical_controls.children = (
            tuple(
                children
            )
        )

    def _settings(
        self,
    ):
        aoi = Path(
            self.aoi.value.strip()
        ).expanduser()

        if (
            self.output_dir.value.strip()
        ):
            output_dir = Path(
                self.output_dir.value.strip()
            ).expanduser()
        else:
            output_dir = (
                aoi.parent
                / (
                    aoi.stem
                    + "_Reference_DEM"
                )
            )

        existing = None
        downloaded_custom = None
        existing_custom = None

        if (
            self.source.value
            == "existing"
        ):
            existing = Path(
                self.existing_dem.value.strip()
            ).expanduser()

            if (
                self.existing_vertical.value
                != "none"
                and (
                    self.existing_model.value
                    == "custom"
                )
            ):
                existing_custom = Path(
                    self.existing_custom_n.value.strip()
                ).expanduser()

        elif (
            self.convert_downloaded.value
            and (
                self.downloaded_model.value
                == "custom"
            )
        ):
            downloaded_custom = Path(
                self.downloaded_custom_n.value.strip()
            ).expanduser()

        return Settings(
            aoi_path=aoi,
            output_dir=output_dir,
            region=self.region.value,
            source=self.source.value,
            resolution_m=float(
                self.resolution.value
            ),
            existing_dem=existing,
            global_buffer_deg=float(
                self.global_buffer.value
            ),
            ign_buffer_m=float(
                self.ign_buffer.value
            ),
            ign_workers=int(
                self.ign_workers.value
            ),
            final_crs_mode=(
                self.final_crs_mode.value
            ),
            custom_crs=(
                self.custom_crs.value.strip()
            ),
            resampling=(
                self.resampling.value
            ),
            convert_downloaded_to_ellipsoid=bool(
                self.convert_downloaded.value
            ),
            downloaded_geoid_model=(
                self.downloaded_model.value
            ),
            downloaded_custom_n_raster=(
                downloaded_custom
            ),
            existing_vertical_conversion=(
                self.existing_vertical.value
            ),
            existing_geoid_model=(
                self.existing_model.value
            ),
            existing_custom_n_raster=(
                existing_custom
            ),
            save_show_geoid_model=bool(
                self.save_show_model.value
            ),
        )

    def _set_progress(
        self,
        value,
        text,
    ):
        self.progress.value = (
            int(
                value
            )
        )

        self.progress_text.value = (
            "<div style='color:#555;'>"
            + html.escape(
                str(
                    text
                )
            )
            + "</div>"
        )

    def _image(
        self,
        path,
    ):
        return widgets.Image(
            value=Path(
                path
            ).read_bytes(),
            format="png",
            layout=widgets.Layout(
                width="100%",
                max_width="1050px",
                height="auto",
            ),
        )

    def _run(
        self,
        _,
    ):
        self.prepare.disabled = (
            True
        )

        self.progress.bar_style = (
            ""
        )

        self.summary.value = (
            ""
        )

        self.qc_box.children = ()
        self.preview_box.children = ()
        self.model_box.children = ()
        self.log_box.children = ()

        try:
            settings = (
                self._settings()
            )

            result = (
                prepare_reference_dem(
                    settings,
                    progress_callback=(
                        self._set_progress
                    ),
                )
            )

            self.progress.bar_style = (
                "success"
            )

            warning_html = (
                ""
            )

            if result[
                "warning"
            ]:
                warning_html = (
                    "<br><br>"
                    "<span style='color:#a05a00;'>"
                    "<b>Resolution note:</b> "
                    + html.escape(
                        result[
                            "warning"
                        ]
                    )
                    + "</span>"
                )

            model_text = (
                geoid_label(
                    result[
                        "model"
                    ]
                )
                if result[
                    "model"
                ]
                else "No vertical conversion"
            )

            self.summary.value = (
                "<div style='margin:10px 0;padding:12px;"
                "border-left:4px solid #2e7d32;"
                "background:#f4fbf4;'>"
                "<b>✓ Final reference DEM completed.</b><br><br>"
                "<b>Source:</b> "
                + html.escape(
                    result[
                        "source_info"
                    ][
                        "label"
                    ]
                )
                + "<br>"
                "<b>Final CRS:</b> "
                + html.escape(
                    result[
                        "final_crs"
                    ].to_string()
                )
                + "<br>"
                "<b>Final vertical reference:</b> "
                + html.escape(
                    result[
                        "final_vertical"
                    ]
                )
                + "<br>"
                "<b>Geoid model:</b> "
                + html.escape(
                    model_text
                )
                + "<br><br>"
                "<b>ONE FINAL DEM:</b><br>"
                "<code>"
                + html.escape(
                    str(
                        result[
                            "final_dem"
                        ]
                    )
                )
                + "</code>"
                + warning_html
                + "<br><br>"
                "<b>Configuration:</b> "
                "<code>"
                + html.escape(
                    str(
                        result[
                            "config_path"
                        ]
                    )
                )
                + "</code>"
                "</div>"
            )

            self.qc_box.children = (
                widgets.HTML(
                    value=(
                        "<b>Final DEM quality control</b><br>"
                        + pd.DataFrame(
                            [
                                result[
                                    "stats"
                                ]
                            ]
                        ).to_html(
                            index=False,
                            border=0,
                            float_format=(
                                lambda value: (
                                    f"{value:.3f}"
                                )
                            ),
                        )
                    )
                ),
            )

            self.preview_box.children = (
                self._image(
                    result[
                        "dem_figure"
                    ][
                        "png"
                    ]
                ),
            )

            if (
                result[
                    "model_path"
                ] is not None
                and result[
                    "model_figure"
                ] is not None
            ):
                self.model_box.children = (
                    widgets.HTML(
                        value=(
                            "<b>Geoid separation model used</b><br>"
                            "<code>"
                            + html.escape(
                                str(
                                    result[
                                        "model_path"
                                    ]
                                )
                            )
                            + "</code><br><br>"
                            "<span style='color:#666;'>"
                            "Contours are labeled in metres and the color "
                            "scale uses the requested terrain-style palette."
                            "</span>"
                        )
                    ),
                    self._image(
                        result[
                            "model_figure"
                        ][
                            "png"
                        ]
                    ),
                )
            else:
                self.model_box.children = (
                    widgets.HTML(
                        value=(
                            "<div style='color:#666;'>"
                            "No saved geoid-model map for this run. "
                            "It is available when vertical conversion "
                            "is selected and the save/show option is enabled."
                            "</div>"
                        )
                    ),
                )

            self.log_box.children = (
                widgets.HTML(
                    value=(
                        "<b>Detailed processing log</b><br>"
                        "<code>"
                        + html.escape(
                            str(
                                result[
                                    "log_path"
                                ]
                            )
                        )
                        + "</code>"
                    )
                ),
            )

        except Exception as exc:
            self.progress.bar_style = (
                "danger"
            )

            self.summary.value = (
                "<div style='margin:10px 0;padding:12px;"
                "border-left:4px solid #b00020;"
                "background:#fff4f4;'>"
                "<b>✗ Processing stopped.</b><br>"
                + html.escape(
                    type(
                        exc
                    ).__name__
                    + ": "
                    + str(
                        exc
                    )
                )
                + "</div>"
            )

        finally:
            self.prepare.disabled = (
                False
            )

    def display(
        self,
    ):
        display(
            self.root
        )

        return self


def reference_dem_setup():
    return ReferenceDEMUI().display()


__all__ = [
    "VERSION",
    "Settings",
    "ReferenceDEMUI",
    "default_downloaded_geoid_model",
    "prepare_reference_dem",
    "reference_dem_setup",
]
