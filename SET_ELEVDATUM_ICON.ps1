# ElevDatum ED logo - non-destructive Windows desktop shortcut icon refresh.
# Changes only the icon associated with an existing shortcut. No Python/Conda or
# installed toolkit files are modified. Supports old and renamed GitHub URLs.
param(
    [string]$ShortcutPath = '',
    [string]$ImagePath = ''
)
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

if (-not $IsWindows -and $PSVersionTable.PSEdition -eq 'Core' -and $env:OS -ne 'Windows_NT') {
    throw 'This helper is for Windows.'
}
if (-not $ShortcutPath) {
    $desktop = [Environment]::GetFolderPath([Environment+SpecialFolder]::DesktopDirectory)
    $newShortcut = Join-Path $desktop 'ElevDatum.lnk'
    $legacyShortcut = Join-Path $desktop 'Geodetic Elevation Toolkit.lnk'
    $ShortcutPath = if (Test-Path -LiteralPath $newShortcut -PathType Leaf) { $newShortcut } else { $legacyShortcut }
}
if (-not (Test-Path -LiteralPath $ShortcutPath -PathType Leaf)) {
    throw "Existing toolkit shortcut not found: $ShortcutPath. Install the toolkit first."
}
$base = Join-Path $env:LOCALAPPDATA 'GeodeticElevationToolkit'
New-Item -ItemType Directory -Path $base -Force | Out-Null
$localImage = Join-Path $base 'ElevDatum-ED-logo.jpg'

if ($ImagePath) {
    if (-not (Test-Path -LiteralPath $ImagePath -PathType Leaf)) {
        throw "Image file not found: $ImagePath"
    }
    Copy-Item -LiteralPath $ImagePath -Destination $localImage -Force
} else {
    $bundled = Join-Path $PSScriptRoot 'assets\ElevDatum-ED-logo.jpg'
    if (Test-Path -LiteralPath $bundled -PathType Leaf) {
        Copy-Item -LiteralPath $bundled -Destination $localImage -Force
    } else {
        $urls = @(
            'https://raw.githubusercontent.com/IslamKOA/elevdatum/main/assets/ElevDatum-ED-logo.jpg',
            'https://raw.githubusercontent.com/IslamKOA/geodetic-elevation-data-toolkit/main/assets/ElevDatum-ED-logo.jpg'
        )
        $received = $false
        foreach ($url in $urls) {
            try {
                Invoke-WebRequest -Uri $url -OutFile $localImage -UseBasicParsing -ErrorAction Stop
                $received = $true
                break
            } catch {
                Write-Host "Unable to retrieve logo from $url; checking alternative."
            }
        }
        if (-not $received) {
            if (-not (Test-Path -LiteralPath $localImage -PathType Leaf)) {
                throw 'Cannot download the official ED logo from either repository address.'
            }
            Write-Warning 'Network unavailable; using previously downloaded ED logo.'
        }
    }
}

# Build an ICO using standard Windows PowerShell/.NET: no Pillow, Python,
# Conda/Micromamba, ASP, or new system package required.
Add-Type -AssemblyName System.Drawing
$image = [System.Drawing.Image]::FromFile($localImage)
try {
    $frames = New-Object System.Collections.ArrayList
    foreach ($n in @(16, 24, 32, 48, 64, 128)) {
        $bitmap = New-Object System.Drawing.Bitmap -ArgumentList @($n, $n)
        try {
            $g = [System.Drawing.Graphics]::FromImage($bitmap)
            try {
                $g.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
                $g.DrawImage($image, 0, 0, $n, $n)
            } finally { $g.Dispose() }
            $stream = New-Object System.IO.MemoryStream
            try {
                $bitmap.Save($stream, [System.Drawing.Imaging.ImageFormat]::Png)
                [void]$frames.Add(@{ Size = $n; Bytes = $stream.ToArray() })
            } finally { $stream.Dispose() }
        } finally { $bitmap.Dispose() }
    }
} finally { $image.Dispose() }

$hash = (Get-FileHash -LiteralPath $localImage -Algorithm SHA256).Hash.Substring(0, 12).ToLowerInvariant()
$iconFile = Join-Path $base ("ElevDatum-ED-" + $hash + ".ico")
$stream = [System.IO.File]::Create($iconFile)
try {
    $writer = New-Object System.IO.BinaryWriter($stream)
    try {
        $writer.Write([UInt16]0)
        $writer.Write([UInt16]1)
        $writer.Write([UInt16]$frames.Count)
        $offset = 6 + (16 * $frames.Count)
        foreach ($frame in $frames) {
            $writer.Write([byte]$frame.Size)
            $writer.Write([byte]$frame.Size)
            $writer.Write([byte]0)
            $writer.Write([byte]0)
            $writer.Write([UInt16]1)
            $writer.Write([UInt16]32)
            $writer.Write([UInt32]$frame.Bytes.Length)
            $writer.Write([UInt32]$offset)
            $offset += $frame.Bytes.Length
        }
        foreach ($frame in $frames) { $writer.Write([byte[]]$frame.Bytes) }
    } finally { $writer.Dispose() }
} finally { $stream.Dispose() }

# Preserve the shortcut's TargetPath, arguments and working directory.
$shell = New-Object -ComObject WScript.Shell
$link = $shell.CreateShortcut($ShortcutPath)
$link.IconLocation = "$iconFile,0"
$link.Save()
# Rename the old Desktop shortcut while keeping its existing target and arguments.
$destination = Join-Path ([IO.Path]::GetDirectoryName($ShortcutPath)) 'ElevDatum.lnk'
if ([IO.Path]::GetFileName($ShortcutPath) -ieq 'Geodetic Elevation Toolkit.lnk' -and
    -not (Test-Path -LiteralPath $destination -PathType Leaf)) {
    Move-Item -LiteralPath $ShortcutPath -Destination $destination
    $ShortcutPath = $destination
}
try {
    Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class ElevDatumIconRefresh {
  [DllImport("shell32.dll")]
  public static extern void SHChangeNotify(uint e, uint f, IntPtr a, IntPtr b);
}
'@ -ErrorAction Stop
    [ElevDatumIconRefresh]::SHChangeNotify(0x08000000, 0, [IntPtr]::Zero, [IntPtr]::Zero)
} catch {
    Write-Host 'If the icon is cached, right-click the Desktop and press Refresh (F5).'
}
Write-Host "ElevDatum desktop icon applied: $iconFile" -ForegroundColor Green
