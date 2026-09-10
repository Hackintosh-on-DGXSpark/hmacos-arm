"""Relocatable project paths, runtime pointers, and storage safety checks."""

import os
from dataclasses import dataclass
from pathlib import Path

# Generated state is kept out of tracked source and off the login name/home.
STATE_DEFAULT_NAME = "artifacts"
RUNS_DIR_NAME = "runs"
CURRENT_POINTER = "current-run"
CURRENT_PID = "current.pid"


@dataclass(frozen=True)
class ProjectPaths:
    root: Path
    state: Path
    sysroot: Path
    bundle: Path
    qemu: Path
    runs: Path

    @classmethod
    def from_environment(cls):
        root = (
            Path(os.environ.get("HMACOS_ROOT", Path(__file__).resolve().parents[2]))
            .expanduser()
            .resolve()
        )
        state = (
            Path(os.environ.get("HMACOS_STATE_DIR", root / STATE_DEFAULT_NAME))
            .expanduser()
            .resolve()
        )
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
        runs = Path(os.environ.get("HMACOS_RUNS_DIR", state / RUNS_DIR_NAME)).expanduser().resolve()
        return cls(root, state, sysroot, bundle, qemu, runs)


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


def current_run(paths):
    """Return the run directory recorded by the last successful launch, if any."""
    pointer = paths.state / CURRENT_POINTER
    if not pointer.is_file() or pointer.is_symlink():
        return None
    name = pointer.read_text().strip()
    if not name or Path(name).name != name:
        return None
    run = paths.runs / name
    return run if run.is_dir() and not run.is_symlink() else None


def record_launch(paths, run, pid):
    paths.state.mkdir(parents=True, exist_ok=True)
    (paths.state / CURRENT_POINTER).write_text(run.name + "\n")
    (paths.state / CURRENT_PID).write_text(f"{pid}\n")


def clear_launch(paths):
    for name in (CURRENT_POINTER, CURRENT_PID):
        pointer = paths.state / name
        if pointer.is_file() and not pointer.is_symlink():
            pointer.unlink()


def validate_baseline(base):
    """Refuse an unverified or symlinked input bundle before any copy."""
    marker = base / "STAGING_COMPLETE"
    if not marker.is_file() or marker.is_symlink():
        raise ValueError("Verified baseline STAGING_COMPLETE marker required")


def validate_run_storage(run, base):
    """Refuse a run that is missing storage or aliases the baseline inode."""
    validate_baseline(base)
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
