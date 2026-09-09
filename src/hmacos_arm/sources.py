"""Fetch hash-pinned public sources into the ignored sysroot and apply patches."""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tarfile
import tempfile
import time
import urllib.request
from pathlib import Path

from .config import ProjectPaths


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def fetch_source(source, sysroot, cache, offline=False):
    destination = sysroot / source["destination"]
    if destination.is_symlink() or not destination.resolve().is_relative_to(sysroot.resolve()):
        raise ValueError("Dependency destination must stay inside the sysroot")
    record = {key: source[key] for key in ("revision", "sha256")}
    stamp = destination / ".hmacos-source.json"
    if destination.exists() and any(destination.iterdir()):
        if stamp.is_file() and json.loads(stamp.read_text()) == record:
            return destination
        raise ValueError(f"Refusing to overwrite unmanaged dependency: {destination}")
    archive = cache / source["archive"]
    if not archive.exists():
        if offline:
            raise ValueError(f"Missing cached archive: {archive}")
        partial = archive.with_name(archive.name + f".part-{os.getpid()}")
        started = time.monotonic()
        with (
            urllib.request.urlopen(source["url"], timeout=30) as response,
            partial.open("xb") as output,
        ):
            while block := response.read(1024 * 1024):
                if time.monotonic() - started > 1200:
                    raise TimeoutError("Source download exceeded 1200 seconds")
                output.write(block)
        if sha256(partial) != source["sha256"]:
            raise ValueError(f"Archive checksum mismatch: {partial}")
        partial.rename(archive)
    if sha256(archive) != source["sha256"]:
        raise ValueError(f"Cached archive checksum mismatch: {archive}")
    with tempfile.TemporaryDirectory(prefix=".source-", dir=sysroot) as staging:
        with tarfile.open(archive) as compressed:
            prefix = source["prefix"]
            if any(
                member.name != prefix and not member.name.startswith(prefix + "/")
                for member in compressed.getmembers()
            ):
                raise ValueError("Unexpected archive root")
            compressed.extractall(staging, filter="data")
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            destination.rmdir()  # Only the previously checked empty submodule directory.
        (Path(staging) / prefix).rename(destination)
    if source.get("overlay"):
        shutil.copytree(sysroot / source["overlay"], destination, dirs_exist_ok=True)
    stamp.write_text(json.dumps(record, sort_keys=True, indent=2) + "\n")
    return destination


def prepare(paths, offline=False):
    manifest = json.loads((paths.root / "deps/sources.lock.json").read_text())
    cache = Path(os.environ.get("HMACOS_ARCHIVE_CACHE", paths.sysroot / "downloads")).resolve()
    paths.sysroot.mkdir(parents=True, exist_ok=True)
    cache.mkdir(parents=True, exist_ok=True)
    for source in manifest["sources"]:
        print(f"Preparing {source['name']} at {source['revision']}", flush=True)
        fetch_source(source, paths.sysroot, cache, offline)
    tree = paths.sysroot / "reims-vgpu"
    changed = False
    for filename in manifest["patches"]:
        patch = str(paths.root / filename)
        check = subprocess.run(["git", "apply", "--check", patch], cwd=tree, capture_output=True)
        if check.returncode == 0:
            subprocess.run(["git", "apply", patch], cwd=tree, check=True)
            changed = True
        else:
            subprocess.run(["git", "apply", "--reverse", "--check", patch], cwd=tree, check=True)
    locked = paths.root / manifest["cargo_lock"]
    destination = tree / "Cargo.lock"
    if changed:
        shutil.copyfile(locked, destination)
    elif not destination.is_file() or sha256(destination) != sha256(locked):
        raise ValueError("Prepared Cargo.lock differs from the recorded dependency lock")
    print(f"Pinned sources and patches ready: {tree}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline", action="store_true", help="use verified cached archives only")
    args = parser.parse_args()
    prepare(ProjectPaths.from_environment(), args.offline)


if __name__ == "__main__":
    main()
