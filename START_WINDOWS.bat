@echo off
setlocal
cd /d "%~dp0"
title Geoid Converter - Python processing server
where py >nul 2>nul
if not errorlevel 1 (
  py -3 -c "import rasterio, geopandas, pyproj, numpy" >nul 2>nul
  if not errorlevel 1 goto RUN_PY
)
where python >nul 2>nul
if errorlevel 1 goto NO_PYTHON
python -c "import rasterio, geopandas, pyproj, numpy" >nul 2>nul
if errorlevel 1 goto DEPS_PYTHON
:RUN_PYTHON
echo.
echo Starting Geoid Converter at http://127.0.0.1:8765/
echo Keep this terminal window open while using the application.
echo.
python geoid_web.py
echo.
echo The processing server stopped. Read any error above.
pause
exit /b
:RUN_PY
echo.
echo Starting Geoid Converter at http://127.0.0.1:8765/
echo Keep this terminal window open while using the application.
echo.
py -3 geoid_web.py
echo.
echo The processing server stopped. Read any error above.
pause
exit /b
:NO_PYTHON
echo Python 3 not found. Install Python from https://www.python.org/downloads/
pause
exit /b 1
:DEPS_PYTHON
echo Python packages are missing. Please run:
echo python -m pip install -r requirements.txt
pause
exit /b 1
