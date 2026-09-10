"""Verify a user-supplied Ventura input bundle; never download Apple software."""

import argparse
import re
from pathlib import Path

from .config import ProjectPaths, sha256

FILES = {"disk.img", "aux.img", "aux.img.trimmed", "vm.json", "AVPBooter.vmapple2.bin"}


def verify_bundle(directory, mark=False):
    manifest = directory / "SHA256SUMS"
    if not manifest.is_file() or manifest.is_symlink():
        raise ValueError("A regular SHA256SUMS manifest is required")
    checksums = {}
    for line in manifest.read_text().splitlines():
        match = re.fullmatch(r"([0-9a-fA-F]{64}) [ *](\S+)", line)
        if not match or match[2] not in FILES or match[2] in checksums:
            raise ValueError("Manifest must name each of the five bundle files exactly once")
        checksums[match[2]] = match[1].lower()
    if set(checksums) != FILES:
        raise ValueError("Incomplete input manifest")
    for name, expected in checksums.items():
        path = directory / name
        if not path.is_file() or path.is_symlink() or sha256(path) != expected:
            raise ValueError(f"Input missing, symlinked, or checksum mismatch: {name}")
        print(f"{name}: verified", flush=True)
    marker = directory / "STAGING_COMPLETE"
    if marker.is_symlink():
        raise ValueError("Completion marker must not be a symlink")
    if mark and not marker.exists():
        with marker.open("x") as output:
            output.write("All five input checksums verified.\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "directory", nargs="?", type=Path, default=ProjectPaths.from_environment().bundle
    )
    parser.add_argument(
        "--mark", action="store_true", help="create STAGING_COMPLETE after successful verification"
    )
    args = parser.parse_args()
    try:
        verify_bundle(args.directory, args.mark)
    except (ValueError, OSError) as error:
        parser.exit(1, f"Bundle verification failed: {error}\n")


if __name__ == "__main__":
    main()
