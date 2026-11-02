#!/usr/bin/env python3
"""Update ElevDatum managed files from a source archive; preserve extra user files."""
import argparse
import json
import pathlib
import py_compile
import shutil
import tempfile
import zipfile

MANIFEST = ".elevdatum-managed.json"
SKIP = {".git", "__pycache__", ".pytest_cache", "outputs", "results", "user_data"}

def update(archive, folder, source):
    folder = pathlib.Path(folder).resolve()
    folder.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="elevdatum-stage-", dir=folder.parent) as td:
        stage = pathlib.Path(td) / "new"
        stage.mkdir()
        with zipfile.ZipFile(archive) as z:
            entries = [i for i in z.infolist() if not i.is_dir()]
            roots = {pathlib.PurePosixPath(i.filename).parts[0] for i in entries}
            if len(roots) != 1:
                raise ValueError("Invalid GitHub ZIP root")
            incoming = {}
            for item in entries:
                parts = pathlib.PurePosixPath(item.filename).parts[1:]
                if not parts or any(x in ("..", ".", "") for x in parts):
                    raise ValueError("Unsafe ZIP path")
                if any(x in SKIP for x in parts) or parts[-1] == MANIFEST:
                    continue
                if (item.external_attr >> 16) & 0o170000 == 0o120000:
                    raise ValueError("Archive symlink prohibited")
                rel = pathlib.Path(*parts)
                incoming[rel.as_posix()] = item
                dest = stage / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                with z.open(item) as src, dest.open("wb") as dst:
                    shutil.copyfileobj(src, dst)
        if not {"geoid_web.py", "geoid_engine.py", "geoid_interface.html", "requirements.txt"}.issubset(incoming):
            raise ValueError("Missing required application files")
        for file in stage.rglob("*.py"):
            py_compile.compile(str(file), cfile=str(pathlib.Path(td) / (file.name + ".pyc")), doraise=True)
        manifest = folder / MANIFEST
        previous = set()
        if manifest.exists():
            previous = set(json.loads(manifest.read_text(encoding="utf-8"))["files"])
            if any(not isinstance(n, str) or pathlib.PurePosixPath(n).is_absolute() or ".." in pathlib.PurePosixPath(n).parts for n in previous):
                raise ValueError("Unsafe manifest")
        changed = previous | set(incoming)
        backup = pathlib.Path(td) / "backup"
        saved = set()
        folder.mkdir(exist_ok=True)
        for name in changed:
            p = folder / name
            if p.is_symlink() or (p.exists() and not p.is_file()):
                raise ValueError("Unsafe installed path: " + name)
            if p.exists():
                q = backup / name
                q.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(p, q)
                saved.add(name)
        old_manifest = manifest.read_bytes() if manifest.exists() else None
        try:
            for name in sorted(changed):
                p = folder / name
                if name in incoming:
                    p.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(stage / name, p)
                elif p.exists():
                    p.unlink()
            manifest.write_text(json.dumps({"source": source, "files": sorted(incoming)}, indent=2), encoding="utf-8")
        except Exception:
            for name in changed:
                p = folder / name
                if name in saved:
                    p.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(backup / name, p)
                elif p.is_file():
                    p.unlink()
            if old_manifest is None:
                manifest.unlink(missing_ok=True)
            else:
                manifest.write_bytes(old_manifest)
            raise
        print(f"ElevDatum: refreshed {len(incoming)} managed files from {source}.")
        print("Additional user files and the Python environment were preserved.")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--archive", required=True)
    ap.add_argument("--target", required=True)
    ap.add_argument("--source", required=True)
    a = ap.parse_args()
    update(a.archive, a.target, a.source)
