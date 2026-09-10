"""Relocatable project paths, run pointers, and storage safety checks."""

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path

BUILD_DIR = "build"
GUEST_IMAGE_DIR = "guest-image"
INSTANCE_DIR = "vm-instance"
BUNDLE_NAME = "ventura-13.6-22G120"
CURRENT_POINTER = ".current-instance"
CURRENT_PID = ".current.pid"


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


@dataclass(frozen=True)
class ProjectPaths:
    root: Path
    build: Path
    guest_image: Path
    bundle: Path
    instances: Path
    qemu: Path

    @classmethod
    def from_environment(cls):
        root = Path(os.environ.get("HMACOS_ROOT", Path(__file__).resolve().parents[2])).resolve()
        build = Path(os.environ.get("HMACOS_BUILD_DIR", root / BUILD_DIR)).resolve()
        guest_image = Path(
            os.environ.get("HMACOS_GUEST_IMAGE_DIR", root / GUEST_IMAGE_DIR)
        ).resolve()
        bundle = Path(os.environ.get("HMACOS_BUNDLE", guest_image / BUNDLE_NAME)).resolve()
        instances = Path(os.environ.get("HMACOS_INSTANCE_DIR", root / INSTANCE_DIR)).resolve()
        qemu = Path(os.environ.get("HMACOS_QEMU", build / "qemu/qemu-system-aarch64")).resolve()
        return cls(root, build, guest_image, bundle, instances, qemu)


def runtime_environment(paths):
    """Restore tools used by Reims while the guest runs (including llvm-dis)."""
    env = dict(os.environ)
    sysroot = Path(env.get("HMACOS_SYSROOT", paths.root / "sysroot")).expanduser().resolve()
    directories = [
        sysroot / "usr/lib/llvm-20/bin",
        sysroot / "usr/bin",
        Path("/usr/lib/llvm-21/bin"),
        Path("/usr/lib/llvm-20/bin"),
    ]
    search = [str(path) for path in directories if path.is_dir()]
    search.extend(env.get("PATH", os.defpath).split(os.pathsep))
    env["PATH"] = os.pathsep.join(dict.fromkeys(search))
    library = sysroot / "usr/lib/aarch64-linux-gnu"
    if library.is_dir():
        env["LD_LIBRARY_PATH"] = str(library) + (
            os.pathsep + env["LD_LIBRARY_PATH"] if env.get("LD_LIBRARY_PATH") else ""
        )
    return env


def current_instance(paths):
    pointer = paths.instances / CURRENT_POINTER
    if not pointer.is_file() or pointer.is_symlink():
        return None
    name = pointer.read_text().strip()
    if not name or Path(name).name != name:
        return None
    instance = paths.instances / name
    return instance if instance.is_dir() and not instance.is_symlink() else None


def record_instance(paths, instance, pid):
    paths.instances.mkdir(parents=True, exist_ok=True)
    (paths.instances / CURRENT_POINTER).write_text(instance.name + "\n")
    (paths.instances / CURRENT_PID).write_text(f"{pid}\n")


def clear_instance(paths):
    for name in (CURRENT_POINTER, CURRENT_PID):
        pointer = paths.instances / name
        if pointer.is_file() and not pointer.is_symlink():
            pointer.unlink()


def validate_baseline(base):
    marker = base / "STAGING_COMPLETE"
    if not marker.is_file() or marker.is_symlink():
        raise ValueError("Verified guest image STAGING_COMPLETE marker required")


def validate_instance_storage(instance, base):
    """Refuse an instance that is missing storage or aliases the image inode."""
    validate_baseline(base)
    if not instance.is_dir() or instance.is_symlink():
        raise ValueError("Prepare a private, non-symlink instance directory first")
    for name in ("disk.img", "aux.img.trimmed"):
        target = instance / name
        if not target.is_file() or target.is_symlink():
            raise ValueError(f"Working copy missing or symlinked: {target}")
        if target.samefile(base / name):
            raise ValueError(f"Refusing to boot guest-image inode: {target}")
        if not os.access(target, os.W_OK):
            raise ValueError(f"Working copy is not writable: {target}")
