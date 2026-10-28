#!/usr/bin/env bash
# ElevDatum v5.0.0 automatic setup (Linux/macOS).
# No Git, system Python, Conda, or preinstalled Micromamba is necessary.
set -euo pipefail

ENV_NAME="geoid_tool"
RELEASE="v5.0.0"
WORKSPACE="$HOME/.local/share/ElevDatum"
FOLDER="$WORKSPACE/$RELEASE"
ENTRY="$FOLDER/geoid_web.py"
SOURCE_URL="https://github.com/IslamKOA/geodetic-elevation-data-toolkit/archive/refs/tags/$RELEASE.zip"
mkdir -p "$WORKSPACE"

say() { printf '\n[ElevDatum] %s\n' "$*"; }
fail() { printf 'ElevDatum setup failed: %s\n' "$*" >&2; exit 1; }
download() {
  if command -v curl >/dev/null 2>&1; then
    curl -fLSs --retry 2 "$1" --output "$2"
  elif command -v wget >/dev/null 2>&1; then
    wget -q --tries=3 -O "$2" "$1"
  else
    fail "Install curl or wget to enable internet downloads."
  fi
}
case "$(uname -s):$(uname -m)" in
  Linux:x86_64|Linux:amd64) platform="linux-64" ;;
  Linux:aarch64|Linux:arm64) platform="linux-aarch64" ;;
  Linux:ppc64le) platform="linux-ppc64le" ;;
  Darwin:x86_64) platform="osx-64" ;;
  Darwin:arm64) platform="osx-arm64" ;;
  *) fail "Unsupported operating system or CPU architecture." ;;
esac

if [[ -z "${MAMBA_ROOT_PREFIX:-}" ]]; then
  MAMBA_ROOT_PREFIX="$HOME/micromamba"
  for root in "$HOME/micromamba" "$HOME/.local/share/mamba" "$HOME/.local/share/micromamba"; do
    if [[ -x "$root/envs/$ENV_NAME/bin/python" ]]; then
      MAMBA_ROOT_PREFIX="$root"
      break
    fi
  done
  export MAMBA_ROOT_PREFIX
fi

manager_paths=()
manager_types=()
add_manager() {
  local type="$1" path="$2" item
  [[ -n "$path" && -f "$path" && -x "$path" ]] || return 0
  for item in "${manager_paths[@]}"; do [[ "$item" == "$path" ]] && return 0; done
  manager_paths+=("$path")
  manager_types+=("$type")
}
for type in micromamba mamba conda; do
  if command -v "$type" >/dev/null 2>&1; then
    add_manager "$type" "$(command -v "$type")"
  fi
done
if [[ -n "${CONDA_EXE:-}" ]]; then add_manager conda "$CONDA_EXE"; fi
if [[ -n "${MAMBA_EXE:-}" ]]; then add_manager mamba "$MAMBA_EXE"; fi
for file in "$HOME/.local/bin/micromamba" "$HOME/micromamba/bin/micromamba" \
  "$HOME/micromamba/micromamba" "$HOME/.local/share/mamba/bin/micromamba"; do
  add_manager micromamba "$file"
done
for prefix in "$HOME/miniforge3" "$HOME/miniconda3" "$HOME/anaconda3" \
  "$HOME/Miniforge3" "$HOME/Miniconda3" "$HOME/Anaconda3" \
  "/opt/conda" "/opt/miniforge3" "/opt/miniconda3"; do
  add_manager conda "$prefix/bin/conda"
  add_manager mamba "$prefix/bin/mamba"
done

selected=""
selected_type=""
first_usable=""
first_usable_type=""
for i in "${!manager_paths[@]}"; do
  path="${manager_paths[$i]}"
  type="${manager_types[$i]}"
  if listing="$("$path" env list --json 2>/dev/null)"; then
    if [[ -z "$first_usable" ]]; then first_usable="$path"; first_usable_type="$type"; fi
    if printf '%s' "$listing" | grep -Fq "/$ENV_NAME\""; then
      selected="$path"
      selected_type="$type"
      break
    fi
  fi
done
if [[ -z "$selected" ]]; then selected="$first_usable"; selected_type="$first_usable_type"; fi
if [[ -z "$selected" ]]; then
  say "No environment manager found. Installing standalone Micromamba."
  command -v tar >/dev/null 2>&1 || fail "The tar utility is needed to extract Micromamba."
  stage="$(mktemp -d)"
  download "https://micro.mamba.pm/api/micromamba/$platform/latest" "$stage/micromamba.tar.bz2"
  (cd "$stage" && tar -xf micromamba.tar.bz2 bin/micromamba) \
    || fail "Micromamba extraction failed; tar needs bzip2 support."
  mkdir -p "$HOME/.local/bin"
  install -m 755 "$stage/bin/micromamba" "$HOME/.local/bin/micromamba"
  rm -rf "$stage"
  selected="$HOME/.local/bin/micromamba"
  selected_type="micromamba"
  "$selected" --version || fail "Downloaded Micromamba cannot run."
fi
say "Using $selected_type: $selected"
listing="$("$selected" env list --json)" || fail "Unable to inspect managed environments."
if ! printf '%s' "$listing" | grep -Fq "/$ENV_NAME\""; then
  say "Creating isolated Python 3.12 geospatial environment ($ENV_NAME)."
  "$selected" create -y -n "$ENV_NAME" --override-channels -c conda-forge \
    python=3.12 numpy scipy rasterio geopandas pyproj requests matplotlib pandas shapely affine
else
  say "Reusing existing $ENV_NAME environment without changing dependencies."
fi

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
cat > "$tmp/verify.py" <<'PY'
import sys
import numpy, scipy, rasterio, geopandas, pyproj
import requests, matplotlib, pandas, shapely, affine
assert sys.version_info >= (3, 10), "Python >=3.10 required"
print("ElevDatum Python:", sys.executable)
print("NumPy:", numpy.__version__, numpy.__file__)
print("SciPy:", scipy.__version__, scipy.__file__)
PY
"$selected" run -n "$ENV_NAME" python "$tmp/verify.py" \
  || fail "Python dependency check failed. Existing environments have not been modified."

# Only download the published, immutable v5.0.0 source when not already installed.
if [[ ! -f "$ENTRY" ]]; then
  [[ ! -e "$FOLDER" ]] || fail "Incomplete existing directory $FOLDER; not overwriting user files."
  say "Downloading the stable ElevDatum v5.0.0 ZIP (no Git needed)."
  download "$SOURCE_URL" "$tmp/source.zip"
  cat > "$tmp/extract.py" <<'PY'
import pathlib, shutil, sys, zipfile
archive, dest = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
unpack = archive.parent / "extracted"
with zipfile.ZipFile(archive) as z:
    z.extractall(unpack)
roots = [p for p in unpack.iterdir() if p.is_dir() and (p / "geoid_web.py").is_file()]
if len(roots) != 1 or dest.exists():
    raise SystemExit("Unexpected source ZIP or existing target directory.")
shutil.move(str(roots[0]), str(dest))
PY
  "$selected" run -n "$ENV_NAME" python "$tmp/extract.py" "$tmp/source.zip" "$FOLDER"
fi
say "ElevDatum is installed at: $FOLDER"
say "Opening: http://127.0.0.1:8765/"
say "Later launch: $selected run -n $ENV_NAME python $ENTRY"
cd "$FOLDER"
if [[ "${ELEVDATUM_NO_LAUNCH:-0}" != "1" ]]; then
  "$selected" run -n "$ENV_NAME" python "$ENTRY"
fi
