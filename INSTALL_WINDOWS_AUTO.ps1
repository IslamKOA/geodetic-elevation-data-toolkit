# One-command Windows installer for Geodetic & Elevation Data Toolkit v5.0.0.
# Review this script before executing. Requires an existing Conda or Micromamba installation.
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
$env:PYTHONNOUSERSITE = "1"
Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue
$release = "v5.0.0"
$base = Join-Path $env:LOCALAPPDATA "GeodeticElevationToolkit"
$folder = Join-Path $base $release
$entry = Join-Path $folder "geoid_web.py"
$envName = "geoid_tool"
$packages = @("python=3.12","numpy","scipy","rasterio","geopandas","pyproj","requests","matplotlib","pandas","shapely","affine")
$conda = Get-Command conda -ErrorAction SilentlyContinue
$micro = Get-Command micromamba -ErrorAction SilentlyContinue
if ($conda) { $manager = "conda" }
elseif ($micro) { $manager = "micromamba" }
else {
  throw "Neither Conda nor Micromamba was found. Install Micromamba using the official guide: https://github.com/IslamKOA/geodetic-elevation-data-toolkit/blob/main/INSTALL_WINDOWS_MICROMAMBA.md"
}
Write-Host "Using $manager (existing environment manager)." -ForegroundColor Cyan
New-Item -ItemType Directory -Path $base -Force | Out-Null
if (-not (Test-Path $entry)) {
  if (Test-Path $folder) { throw "Installation folder exists but is incomplete: $folder. Please inspect before rerunning." }
  $temp = Join-Path $base ("download-" + [guid]::NewGuid().ToString("N"))
  New-Item -ItemType Directory -Path $temp | Out-Null
  try {
    $archive = Join-Path $temp "source.zip"
    Invoke-WebRequest -Uri "https://github.com/IslamKOA/geodetic-elevation-data-toolkit/archive/refs/tags/$release.zip" -OutFile $archive
    Expand-Archive -Path $archive -DestinationPath (Join-Path $temp "extracted")
    $source = Get-ChildItem -Path (Join-Path $temp "extracted") -Directory | Where-Object { Test-Path (Join-Path $_.FullName "geoid_web.py") } | Select-Object -First 1
    if (-not $source) { throw "Invalid release package: geoid_web.py missing." }
    Move-Item -LiteralPath $source.FullName -Destination $folder
  } finally { Remove-Item -LiteralPath $temp -Recurse -Force -ErrorAction SilentlyContinue }
}
Write-Host "Toolkit source: $folder" -ForegroundColor Green
$check = & $manager run -n $envName python -c "import numpy, scipy, rasterio, geopandas, pyproj" 2>&1
if ($LASTEXITCODE -ne 0) {
  $environments = & $manager env list --json | ConvertFrom-Json
  $existing = @($environments.envs | Where-Object { (Split-Path $_ -Leaf) -eq $envName })
  if ($existing.Count -gt 0) {
    throw "An existing '$envName' environment failed its dependency check. It was NOT modified. See INSTALL_WINDOWS_CONDA_OR_MICROMAMBA.md to repair it, or create a clean environment."
  }
  Write-Host "Creating the $envName environment..." -ForegroundColor Cyan
  & $manager create -n $envName --override-channels -c conda-forge @packages -y
  if ($LASTEXITCODE -ne 0) { throw "Environment creation failed." }
}
& $manager run -n $envName python -c "import sys,numpy,scipy,rasterio,geopandas,pyproj; print('Python:',sys.executable); print('NumPy:',numpy.__version__,numpy.__file__); print('SciPy:',scipy.__version__,scipy.__file__)"
if ($LASTEXITCODE -ne 0) { throw "Environment validation failed." }
$launcher = Join-Path $base "Launch Geodetic Toolkit.cmd"
$contents = @"
@echo off
setlocal
set "PYTHONNOUSERSITE=1"
set "PYTHONPATH="
cd /d "$folder"
echo Starting Geodetic and Elevation Data Toolkit...
start "" "http://127.0.0.1:8765/"
$manager run -n $envName python geoid_web.py
echo.
echo Server stopped. Inspect any error above.
pause
"@
Set-Content -LiteralPath $launcher -Value $contents -Encoding ASCII
Write-Host "Installation complete. Launcher: $launcher" -ForegroundColor Green
Write-Host "Run the launcher at any time; no manual ZIP extraction or folder setup needed."
Start-Process -FilePath $launcher
