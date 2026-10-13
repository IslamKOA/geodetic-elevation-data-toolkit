@echo off
setlocal
cd /d "%~dp0"
title Geodetic and Elevation Data Toolkit - Local Server
rem Prevent AppData\Roaming\Python packages from overriding active environment.
set "PYTHONNOUSERSITE=1"
set "PYTHONPATH="
rem Prefer the Python interpreter in the currently activated Conda/Micromamba environment.
where python >nul 2>nul
if errorlevel 1 goto NO_PYTHON
python -c "import sys, numpy, scipy, rasterio, geopandas, pyproj; print('Python:', sys.executable); print('NumPy:',numpy.__version__,numpy.__file__); print('SciPy:',scipy.__version__,scipy.__file__)" 
if errorlevel 1 goto DEPS_PYTHON
echo.
echo Launching toolkit at http://127.0.0.1:8765/
echo Keep this terminal window open.
echo.
python geoid_web.py
echo.
echo The processing server has stopped. Review errors above if needed.
pause
exit /b
:NO_PYTHON
echo Python not found. Activate your geoid_tool Conda or Micromamba environment first.
echo See INSTALL_WINDOWS_CONDA_OR_MICROMAMBA.md
pause
exit /b 1
:DEPS_PYTHON
echo Python dependencies could not be imported together.
echo Activate geoid_tool then consult INSTALL_WINDOWS_CONDA_OR_MICROMAMBA.md
pause
exit /b 1
