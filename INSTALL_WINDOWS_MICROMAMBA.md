# Windows installation from scratch — Micromamba

This guide is for users who **do not have Conda, Miniconda, Micromamba or Python installed**. Micromamba manages Python and the compiled geospatial libraries; you do **not** need to separately install Python.

## 1. Download the software

Open the [official v5.0.0 release](https://github.com/IslamKOA/geodetic-elevation-data-toolkit/releases/tag/v5.0.0), download **Source code (zip)**, and extract it to a normal folder such as `Documents\geodetic-elevation-data-toolkit-5.0.0`. Do not run the application from inside the compressed ZIP.

## 2. Install Micromamba on Windows

Open **PowerShell** from the Windows Start menu (a normal user shell is sufficient). Follow the official [Micromamba Windows installation documentation](https://mamba.readthedocs.io/en/stable/installation/micromamba-installation.html).

To use its official Windows installer, run:

```powershell
Invoke-Expression ((Invoke-WebRequest -Uri https://micro.mamba.pm/install.ps1 -UseBasicParsing).Content)
```

Only run this command if you trust the linked official installer; you may review the [installation script](https://github.com/mamba-org/micromamba-releases/blob/main/install.ps1) first. When prompted, agree to **initialize PowerShell**. Close PowerShell completely, open a **new** PowerShell window, and check:

```powershell
micromamba --version
```

If it says `micromamba` is not recognized, reopen PowerShell and try `& "$env:LOCALAPPDATA\micromamba\micromamba.exe" --version`. If that works, follow the installer output to initialize the shell, then reopen PowerShell. Do not modify your system-wide Python installation.

## 3. Create the scientific environment (once)

Paste the following command in PowerShell:

```powershell
micromamba create -n geoid_tool -c conda-forge python=3.12 numpy scipy rasterio geopandas pyproj requests matplotlib pandas shapely affine -y
```

This may take several minutes and requires an internet connection. You do not need Anaconda or a separate Python installation.

## 4. Start the complete local application

```powershell
micromamba activate geoid_tool
cd "C:\Users\YourName\Documents\geodetic-elevation-data-toolkit-5.0.0"
python geoid_web.py
```

Replace the example folder path with your actual extracted folder. Keep the PowerShell terminal open. In a browser visit **http://127.0.0.1:8765/**.

To stop the application, press **Ctrl+C** in PowerShell. To launch again later, activate `geoid_tool`, navigate to the project directory, and run `python geoid_web.py`.

**Alternative without activation:** `micromamba run -n geoid_tool python geoid_web.py` from the software directory.

## 5. Verify the installation

From the same directory and environment, run:

```powershell
python release_smoke_test.py
```

A passing test checks sample RAF20 point, AOI and raster calculations. It is not a substitute for independent geodetic accuracy validation.

## Troubleshooting

- **Micromamba is not recognized:** restart PowerShell after installation, or use the full executable path above.
- **Activate fails:** run `micromamba shell init -s powershell -r "$env:USERPROFILE\micromamba"`, close PowerShell and reopen it. If your installer selected a different root directory, use that root instead.
- **Cannot connect to the application:** start `python geoid_web.py` and keep PowerShell open; check error messages in the terminal.
- **Port 8765 is already used:** close a previously running toolkit server.
- **Missing geodetic grids:** EGM96/EGM2008 may need PROJ grid downloads; verify network access and selected model coverage.
- **Windows launcher:** `START_WINDOWS.bat` works when the active/discoverable Python has the required packages. The explicit Micromamba launch steps above are more reliable for a new installation.

For the scientific models, features, data-source limits, citation, and complete documentation, see the [main README](README.md).
