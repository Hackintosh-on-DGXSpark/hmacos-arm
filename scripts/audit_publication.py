#!/usr/bin/env python3
"""Check the Git index for private/generated data before committing or pushing."""

import re
import subprocess
import sys
from pathlib import PurePosixPath


def main():
    names = subprocess.check_output(["git", "ls-files", "-z"]).decode().split("\0")
    forbidden_roots = {"artifacts", "sysroot", "packages", "logs", ".venv", "build", "dist"}
    forbidden_suffixes = {
        ".img",
        ".qcow2",
        ".raw",
        ".iso",
        ".dmg",
        ".cdr",
        ".ipsw",
        ".bin",
        ".mtlb",
        ".air",
        ".spv",
        ".png",
        ".jpg",
        ".pdf",
    }
    secrets = re.compile(
        rb"(?m)^-----BEGIN [A-Z ]*PRIVATE KEY-----|gh[pousr]_[A-Za-z0-9]{20,}|glpat-[A-Za-z0-9_-]{20,}"
    )
    failures = []
    checked = 0
    for name in filter(None, names):
        path = PurePosixPath(name)
        if (
            path.parts[0] in forbidden_roots
            or path.suffix.lower() in forbidden_suffixes
            or path.name.startswith(("session-", ".env"))
            or "Xauthority" in name
            or path.name in {"vm.json", "vnc.passwd"}
        ):
            failures.append(f"private/generated path: {name}")
            continue
        data = subprocess.check_output(["git", "show", f":{name}"])
        if len(data) > 2 * 1024 * 1024 or b"\0" in data:
            failures.append(f"unexpected binary/large file: {name}")
        if secrets.search(data):
            failures.append(f"credential-shaped content: {name}")
        checked += 1
    if not checked and not failures:
        failures.append("No staged project files to audit")
    if failures:
        print("\n".join(failures), file=sys.stderr)
        return 1
    print(
        f"Publication audit passed for {checked} staged text files. Manual review is still required."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
