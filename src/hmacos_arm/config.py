"""Relocatable project paths and storage safety checks."""

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ProjectPaths:
    root: Path
    state: Path
    sysroot: Path
    bundle: Path
    qemu: Path

    @classmethod
    def from_environment(cls):
        root = (
            Path(os.environ.get("HMACOS_ROOT", Path(__file__).resolve().parents[2]))
            .expanduser()
            .resolve()
        )
        state = Path(os.environ.get("HMACOS_STATE_DIR", root / "artifacts")).expanduser().resolve()
        sysroot = Path(os.environ.get("HMACOS_SYSROOT", root / "sysroot")).expanduser().resolve()
        bundle = (
            Path(os.environ.get("HMACOS_BUNDLE", state / "ventura-13.6-22G120"))
            .expanduser()
            .resolve()
        )
        qemu = (
            Path(
                os.environ.get(
                    "HMACOS_QEMU", sysroot / "reims-vgpu/vendor/qemu/build/qemu-system-aarch64"
                )
            )
            .expanduser()
            .resolve()
        )
        return cls(root, state, sysroot, bundle, qemu)


def tool_environment(paths):
    env = dict(os.environ)
    directories = [
        paths.sysroot / "usr/lib/llvm-20/bin",
        Path("/usr/lib/llvm-20/bin"),
        paths.sysroot / "usr/bin",
        paths.sysroot / "build-venv/bin",
        paths.sysroot / "cargo/bin",
    ]
    search = [str(path) for path in directories if path.is_dir()]
    search.extend(part for part in (env.get("PATH") or os.defpath).split(os.pathsep) if part)
    env["PATH"] = os.pathsep.join(dict.fromkeys(search))
    library = paths.sysroot / "usr/lib/aarch64-linux-gnu"
    if library.is_dir():
        env["LD_LIBRARY_PATH"] = str(library) + (
            os.pathsep + env["LD_LIBRARY_PATH"] if env.get("LD_LIBRARY_PATH") else ""
        )
    env.setdefault("RUSTUP_HOME", str(paths.sysroot / "rustup"))
    env.setdefault("CARGO_HOME", str(paths.sysroot / "cargo"))
    env["HMACOS_ROOT"] = str(paths.root)
    return env


def validate_run_storage(run, base):
    marker = base / "STAGING_COMPLETE"
    if not marker.is_file() or marker.is_symlink():
        raise ValueError("Verified baseline STAGING_COMPLETE marker required")
    if not run.is_dir() or run.is_symlink():
        raise ValueError("Prepare a private, non-symlink run directory first")
    for name in ("disk.img", "aux.img.trimmed"):
        target = run / name
        if not target.is_file() or target.is_symlink():
            raise ValueError(f"Working copy missing or symlinked: {target}")
        if target.samefile(base / name):
            raise ValueError(f"Refusing to boot baseline inode: {target}")
        if not os.access(target, os.W_OK):
            raise ValueError(f"Working copy is not writable: {target}")
