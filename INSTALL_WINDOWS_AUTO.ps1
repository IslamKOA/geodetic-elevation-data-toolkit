# ElevDatum (Geodetic & Elevation Data Toolkit) v5.0.0: automatic Windows installation.
# No preinstalled Python, Git, Conda, Mamba or Micromamba is required.
# Reuse working geoid_tool environments; keep data and other environments unchanged.
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
if (-not [Environment]::Is64BitOperatingSystem) { throw "ElevDatum requires 64-bit Windows." }
$env:PYTHONNOUSERSITE = "1"
Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue

$release = "v5.0.0"
$base = Join-Path $env:LOCALAPPDATA "GeodeticElevationToolkit"
$folder = Join-Path $base $release
$entry = Join-Path $folder "geoid_web.py"
$envName = "geoid_tool"
$packages = @("python=3.12","numpy","scipy","rasterio","geopandas","pyproj","requests","matplotlib","pandas","shapely","affine")
New-Item -ItemType Directory -Path $base -Force | Out-Null

# Locate existing managers even if their executables are absent from PATH.
$script:candidates = New-Object System.Collections.ArrayList
function Add-ManagerCandidate([string]$Executable, [string]$Kind) {
  if (-not $Executable -or -not (Test-Path -LiteralPath $Executable -PathType Leaf)) { return }
  $fullPath = [IO.Path]::GetFullPath($Executable)
  foreach ($candidate in $script:candidates) {
    if ($candidate.Exe -ieq $fullPath) { return }
  }
  [void]$script:candidates.Add(@{ Exe = $fullPath; Name = $Kind })
}
foreach ($kind in @("micromamba","mamba","conda")) {
  foreach ($candidate in @(Get-Command -Name $kind -CommandType Application -All -ErrorAction SilentlyContinue)) {
    if ($candidate -and $candidate.Source) { Add-ManagerCandidate $candidate.Source $kind }
  }
}
if ($env:CONDA_EXE) { Add-ManagerCandidate $env:CONDA_EXE "conda" }
if ($env:MAMBA_EXE) { Add-ManagerCandidate $env:MAMBA_EXE "mamba" }
foreach ($path in @(
    (Join-Path $env:LOCALAPPDATA "micromamba\micromamba.exe"),
    (Join-Path $HOME "micromamba\micromamba.exe"),
    (Join-Path $HOME "miniforge3\condabin\conda.bat"),
    (Join-Path $HOME "miniforge3\Scripts\conda.exe"),
    (Join-Path $HOME "miniconda3\condabin\conda.bat"),
    (Join-Path $HOME "miniconda3\Scripts\conda.exe"),
    (Join-Path $HOME "anaconda3\condabin\conda.bat"),
    (Join-Path $HOME "anaconda3\Scripts\conda.exe"),
    (Join-Path $env:LOCALAPPDATA "miniconda3\condabin\conda.bat"),
    (Join-Path $env:LOCALAPPDATA "miniforge3\condabin\conda.bat")
)) {
  $kind = if ($path -match "micromamba") { "micromamba" } else { "conda" }
  Add-ManagerCandidate $path $kind
}

# Select an existing Micromamba root if it already contains the toolkit environment.
# The root is set only for this PowerShell process; no system PATH or profile changes.
if (-not $env:MAMBA_ROOT_PREFIX) {
  $roots = @((Join-Path $HOME "micromamba"), (Join-Path $env:LOCALAPPDATA "micromamba"))
  $root = $roots[0]
  foreach ($candidateRoot in $roots) {
    if (Test-Path -LiteralPath (Join-Path $candidateRoot "envs\$envName\python.exe") -PathType Leaf) {
      $root = $candidateRoot
      break
    }
  }
  $env:MAMBA_ROOT_PREFIX = $root
}

$manager = $null
$firstUsable = $null
foreach ($candidate in $script:candidates) {
  try {
    $rawInfo = & $candidate.Exe env list --json 2>$null
    if ($LASTEXITCODE -ne 0) { continue }
    $envInfo = ($rawInfo | Out-String) | ConvertFrom-Json
    if (-not $envInfo.envs) { continue }
    if (-not $firstUsable) { $firstUsable = $candidate }
    $match = @($envInfo.envs | Where-Object { (Split-Path -Path $_ -Leaf) -eq $envName })
    if ($match.Count -gt 0) {
      $manager = $candidate
      Write-Host "Found an existing $envName environment managed by $($manager.Name)." -ForegroundColor Cyan
      break
    }
  } catch {
    Write-Warning "Skipping unusable environment manager: $($candidate.Exe)"
  }
}
if (-not $manager) { $manager = $firstUsable }

# Bootstrap only when no usable existing environment manager is present.
if (-not $manager) {
  Write-Host "No usable Conda/Mamba/Micromamba detected. Installing standalone Micromamba automatically..." -ForegroundColor Cyan
  $binDir = Join-Path $env:LOCALAPPDATA "micromamba"
  $micromambaExe = Join-Path $binDir "micromamba.exe"
  New-Item -ItemType Directory -Path $binDir -Force | Out-Null
  $arch = if ($env:PROCESSOR_ARCHITECTURE -eq "ARM64" -or $env:PROCESSOR_ARCHITEW6432 -eq "ARM64") { "arm64" } else { "64" }
  $downloadUrl = "https://github.com/mamba-org/micromamba-releases/releases/latest/download/micromamba-win-$arch"
  $tempExe = Join-Path $binDir ("micromamba-" + [Guid]::NewGuid().ToString("N") + ".exe")
  try {
    Invoke-WebRequest -Uri $downloadUrl -OutFile $tempExe -UseBasicParsing -ErrorAction Stop
    if ((Get-Item -LiteralPath $tempExe).Length -lt 1000000) { throw "The downloaded Micromamba executable is incomplete." }
    & $tempExe --version
    if ($LASTEXITCODE -ne 0) { throw "The downloaded Micromamba executable could not run." }
    Move-Item -LiteralPath $tempExe -Destination $micromambaExe -Force
  } finally {
    if (Test-Path -LiteralPath $tempExe) { Remove-Item -LiteralPath $tempExe -Force -ErrorAction SilentlyContinue }
  }
  $manager = @{ Exe = $micromambaExe; Name = "micromamba" }
}
Write-Host "ElevDatum environment manager: $($manager.Name) ($($manager.Exe))" -ForegroundColor Green

$rawInfo = & $manager.Exe env list --json
if ($LASTEXITCODE -ne 0) { throw "Cannot list environments using $($manager.Exe)." }
$envInfo = ($rawInfo | Out-String) | ConvertFrom-Json
$existing = @($envInfo.envs | Where-Object { (Split-Path -Path $_ -Leaf) -eq $envName })
if ($existing.Count -eq 0) {
  Write-Host "Creating dedicated $envName environment and installing Python 3.12 + scientific dependencies..." -ForegroundColor Cyan
  & $manager.Exe create -n $envName --override-channels -c conda-forge @packages -y
  if ($LASTEXITCODE -ne 0) { throw "Creation of the isolated $envName environment failed." }
} else {
  Write-Host "Reusing the existing $envName environment without reinstalling its dependencies." -ForegroundColor Cyan
}

# Read the real Python path from the chosen manager. Never use a system python.exe.
$rawInfo = & $manager.Exe env list --json
if ($LASTEXITCODE -ne 0) { throw "Cannot inspect the Python environment after setup." }
$envInfo = ($rawInfo | Out-String) | ConvertFrom-Json
$prefixes = @($envInfo.envs | Where-Object { (Split-Path -Path $_ -Leaf) -eq $envName })
if ($prefixes.Count -ne 1) { throw "Expected exactly one $envName environment for the selected manager, found $($prefixes.Count)." }
$envPrefix = [string]$prefixes[0]
$pythonExe = Join-Path $envPrefix "python.exe"
if (-not (Test-Path -LiteralPath $pythonExe -PathType Leaf)) { throw "The managed Python executable is missing: $pythonExe" }
$checkScript = Join-Path $base ("elevdatum-python-check-" + [Guid]::NewGuid().ToString("N") + ".py")
@'
import sys
import numpy, scipy, rasterio, geopandas, pyproj
import requests, matplotlib, pandas, shapely, affine
assert sys.version_info >= (3, 10), "ElevDatum requires Python >=3.10"
print("ElevDatum Python:", sys.executable, sys.version)
print("NumPy:", numpy.__version__, numpy.__file__)
print("SciPy:", scipy.__version__, scipy.__file__)
'@ | Set-Content -LiteralPath $checkScript -Encoding ASCII
try {
  & $pythonExe $checkScript
  if ($LASTEXITCODE -ne 0) {
    throw "The existing $envName environment failed validation. No packages were changed in it. See INSTALL_WINDOWS_CONDA_OR_MICROMAMBA.md for repair steps."
  }
} finally {
  Remove-Item -LiteralPath $checkScript -Force -ErrorAction SilentlyContinue
}
Write-Host "ElevDatum Python dependencies verified." -ForegroundColor Green

# Keep the original, published v5.0.0 software source pinned for reproducibility.
# A Git installation is never required: PowerShell downloads the source ZIP itself.
if (-not (Test-Path -LiteralPath $entry -PathType Leaf)) {
  if (Test-Path -LiteralPath $folder) {
    throw "Installation folder exists but is incomplete: $folder. Nothing was deleted; inspect this folder before retrying."
  }
  $temp = Join-Path $base ("download-" + [Guid]::NewGuid().ToString("N"))
  New-Item -ItemType Directory -Path $temp | Out-Null
  try {
    $archive = Join-Path $temp "source.zip"
    Invoke-WebRequest -Uri "https://github.com/IslamKOA/geodetic-elevation-data-toolkit/archive/refs/tags/$release.zip" -OutFile $archive -UseBasicParsing -ErrorAction Stop
    Expand-Archive -LiteralPath $archive -DestinationPath (Join-Path $temp "extracted")
    $source = Get-ChildItem -LiteralPath (Join-Path $temp "extracted") -Directory |
      Where-Object { Test-Path -LiteralPath (Join-Path $_.FullName "geoid_web.py") } |
      Select-Object -First 1
    if (-not $source) { throw "Downloaded source ZIP is missing geoid_web.py." }
    Move-Item -LiteralPath $source.FullName -Destination $folder
  } finally {
    Remove-Item -LiteralPath $temp -Recurse -Force -ErrorAction SilentlyContinue
  }
}
Write-Host "ElevDatum scientific source: $folder" -ForegroundColor Green

$waitScript = Join-Path $base "Open Toolkit When Ready.ps1"
$waitContent = @'
$deadline = (Get-Date).AddSeconds(120)
while ((Get-Date) -lt $deadline) {
  try {
    $client = New-Object System.Net.Sockets.TcpClient
    $result = $client.BeginConnect("127.0.0.1",8765,$null,$null)
    if ($result.AsyncWaitHandle.WaitOne(500)) {
      $client.EndConnect($result)
      $client.Close()
      Start-Process "http://127.0.0.1:8765/"
      exit 0
    }
    $client.Close()
  } catch { }
  Start-Sleep -Seconds 1
}
Write-Warning "Toolkit server did not start within two minutes. Check the server window."
'@
Set-Content -LiteralPath $waitScript -Value $waitContent -Encoding UTF8
$launcher = Join-Path $base "Launch Geodetic Toolkit.cmd"
$contents = @"
@echo off
setlocal
set "PYTHONNOUSERSITE=1"
set "PYTHONPATH="
cd /d "$folder"
set "PATH=$envPrefix\Library\bin;$envPrefix\Scripts;$envPrefix;%PATH%"
set "CONDA_PREFIX=$envPrefix"
echo Starting Geodetic and Elevation Data Toolkit...
start "" powershell -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "$waitScript"
"$pythonExe" geoid_web.py
echo.
echo Server stopped. Inspect any error above.
pause
"@
Set-Content -LiteralPath $launcher -Value $contents -Encoding ASCII
$desktop = [Environment]::GetFolderPath([Environment+SpecialFolder]::DesktopDirectory)
$legacyShortcut = Join-Path $desktop "Geodetic Elevation Toolkit.lnk"
$shortcut = Join-Path $desktop "ElevDatum.lnk"
# Migrate the original shortcut name instead of leaving duplicate launchers.
if ((Test-Path -LiteralPath $legacyShortcut -PathType Leaf) -and
    -not (Test-Path -LiteralPath $shortcut -PathType Leaf)) {
  Move-Item -LiteralPath $legacyShortcut -Destination $shortcut
}
$wsh = New-Object -ComObject WScript.Shell
$link = $wsh.CreateShortcut($shortcut)
$link.TargetPath = $launcher
$link.WorkingDirectory = $folder
$link.Description = "ElevDatum - Geodetic & Elevation Data Toolkit v5.0.0"
$link.Save()
# Apply the current ED branding independently of the pinned v5.0.0 source ZIP.
# This only changes the shortcut icon, and cannot abort an otherwise valid installation.
try {
  $iconUpdater = Join-Path $base "SET_ELEVDATUM_ICON.ps1"
  $iconDownloaded = $false
  foreach ($url in @(
      "https://raw.githubusercontent.com/IslamKOA/elevdatum/main/SET_ELEVDATUM_ICON.ps1",
      "https://raw.githubusercontent.com/IslamKOA/geodetic-elevation-data-toolkit/main/SET_ELEVDATUM_ICON.ps1")) {
    try {
      Invoke-WebRequest -Uri $url -OutFile $iconUpdater -UseBasicParsing -ErrorAction Stop
      $iconDownloaded = $true
      break
    } catch { }
  }
  if ($iconDownloaded) {
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $iconUpdater -ShortcutPath $shortcut
    if ($LASTEXITCODE -ne 0) { Write-Warning "ED shortcut icon update was unsuccessful; the normal Desktop launcher remains valid." }
  } else {
    Write-Warning "Unable to download the ED shortcut icon updater. The normal launcher remains valid."
  }
} catch {
  Write-Warning ("Non-critical ED icon update: " + $_.Exception.Message)
}
Write-Host "Installation complete. Desktop shortcut: $shortcut" -ForegroundColor Green
Write-Host "Double-click this shortcut to open the toolkit in your browser after the local server starts."
Start-Process -FilePath $launcher
