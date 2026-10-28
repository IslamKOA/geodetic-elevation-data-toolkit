# Windows installation — Conda or Micromamba (v5.0.0)

> **Automatic installation recommended:** If you do not have Git, Python, Conda or Micromamba, use the [automatic Windows installer](INSTALL_WINDOWS_AUTO.ps1). It bootstraps standalone Micromamba and Python automatically, without modifying unrelated environments. Open PowerShell:
>
> `irm https://raw.githubusercontent.com/IslamKOA/geodetic-elevation-data-toolkit/main/INSTALL_WINDOWS_AUTO.ps1 | iex`
>
> The instructions below are an **optional manual alternative** for advanced users.


**Choose ONE environment manager.** If you already have Miniconda/Anaconda, use **Conda**. If you already have Micromamba, use **Micromamba**. They install the same scientific Python libraries; no need to install both. If you have neither, follow the [Micromamba installation instructions](INSTALL_WINDOWS_MICROMAMBA.md) first.

## 1. Download the application

Download the [stable v5.0.0 source ZIP](https://github.com/IslamKOA/geodetic-elevation-data-toolkit/archive/refs/tags/v5.0.0.zip) and **extract it**. Open PowerShell (or Anaconda PowerShell Prompt for Conda). Navigate to the extracted directory containing `geoid_web.py` — not its parent ZIP directory.

## 2. Create the environment (once, choose ONE command)

**If Conda is installed:**
```powershell
conda create -n geoid_tool --override-channels -c conda-forge python=3.12 numpy scipy rasterio geopandas pyproj requests matplotlib pandas shapely affine -y
```

**If Micromamba is installed:**
```powershell
micromamba create -n geoid_tool --override-channels -c conda-forge python=3.12 numpy scipy rasterio geopandas pyproj requests matplotlib pandas shapely affine -y
```

Do **not** run both commands. Do not install these geospatial packages again with `pip install --user`: that can cause conflicting NumPy/SciPy versions.

## 3. Activate the environment (every new terminal)

**Conda:**
```powershell
conda activate geoid_tool
```
**Micromamba:**
```powershell
micromamba activate geoid_tool
```

**Then, for EITHER manager, run:**
```powershell
$env:PYTHONNOUSERSITE = "1"
Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue
python -c "import sys, numpy, scipy, rasterio, geopandas, pyproj; print('Python:',sys.executable); print('NumPy:',numpy.__version__,numpy.__file__); print('SciPy:',scipy.__version__,scipy.__file__)"
```

**Check the output:** Python, NumPy and SciPy paths must all point inside `geoid_tool`. If NumPy points to `AppData\Roaming\Python`, your user-site NumPy is interfering. `PYTHONNOUSERSITE=1` prevents this. The above commands only change the current PowerShell session.

## 4. Launch the toolkit

Navigate to the **folder containing `geoid_web.py`**. You can use File Explorer: open that folder, click the address bar, type `powershell` and press Enter; then activate the environment using step 3 in that terminal.

```powershell
python geoid_web.py
```

Open **http://127.0.0.1:8765/** in the browser. Keep the terminal open. Stop with Ctrl+C.

**Launcher alternative:** after activating `geoid_tool` in PowerShell, run `.\START_WINDOWS.bat` from the folder. Launching the batch file from an unrelated terminal may select a different Python interpreter.

## 5. Test the installation (recommended)

```powershell
python release_smoke_test.py
```

This checks RAF20 point, raster and AOI sample calculations and does not certify independent geodetic accuracy.

## Troubleshooting

- **`numpy has no attribute long` / SciPy compatibility warnings:** Run Step 3 again and verify that **both** modules are loaded from `geoid_tool`. No need to delete the environment first.
- **`conda` or `micromamba` not recognized:** reopen the corresponding installed terminal or follow that manager's installation instructions.
- **`geoid_web.py` not found:** your current folder is not the extracted directory containing the script.
- **Browser cannot connect:** read terminal output, confirm the application is still running, and check that port 8765 is available.
- **`py -3` launches wrong Python:** use `python geoid_web.py` after activation; do not use `py -3`.
- **Missing grids or failed DEM downloads:** check internet access, model coverage, provider availability and license conditions.

**Note:** The official v5.0.0 ZIP is an immutable release; these updated setup instructions and the safer launcher apply to the current GitHub `main` branch. The PowerShell commands above also work with the released source.
