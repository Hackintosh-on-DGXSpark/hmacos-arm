"""Build the QEMU argv and graphics environment for one VMApple boot.

This module owns *what to run* only. Process lifecycle, the firmware handoff
environment, and result recording live in :mod:`hmacos_arm.supervisor`.
"""

import os
import shutil
import subprocess
from pathlib import Path

from .desktop import physical_x11_environment

RENDERERS = ("none", "lavapipe", "nvidia")
GUEST_RAM = "8G"
GUEST_RAM_ALIGNMENT = 16384


def check_shader_tools() -> dict[str, dict[str, str]]:
    """Reims invokes these tools during rendering, even with a prebuilt QEMU."""
    tools = {}
    for name in ("llvm-dis", "spirv-val"):
        override = f"METAL2VULKAN_{name.upper().replace('-', '_')}"
        selected = os.environ.get(override, name)
        executable = shutil.which(selected)
        if executable is None:
            raise RuntimeError(
                f"Missing runtime shader tool {name}: {selected}. "
                f"Check sysroot/PATH or {override}; Reims cannot render without it."
            )
        try:
            result = subprocess.run(
                [executable, "--version"], capture_output=True, text=True, timeout=10
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise RuntimeError(f"Cannot run runtime shader tool {name}: {error}") from error
        if result.returncode:
            raise RuntimeError(
                f"Runtime shader tool {name} failed ({result.returncode}): "
                f"{result.stderr.strip() or result.stdout.strip()}"
            )
        tools[name] = {
            "path": executable,
            "version": next(iter(result.stdout.splitlines()), ""),
        }
    return tools


def prepare_render_environment(run: Path, renderer: str) -> None:
    """Apply renderer environment in place; graphics always uses the physical X11 session."""
    if renderer == "none":
        return
    if renderer not in RENDERERS:
        raise ValueError(f"unknown renderer: {renderer}")
    os.environ.update(physical_x11_environment())
    (run / "tmp").mkdir(mode=0o700, exist_ok=True)
    os.environ.update(
        {
            "VK_DRIVER_FILES": f"/usr/share/vulkan/icd.d/{'nvidia' if renderer == 'nvidia' else 'lvp'}_icd.json",
            "WINIT_UNIX_BACKEND": "x11",
            "TMPDIR": str(run / "tmp"),
            "XDG_CACHE_HOME": str(run / "tmp/cache"),
            "MESA_SHADER_CACHE_DIR": str(run / "tmp/mesa-shader-cache"),
        }
    )
    os.environ.pop("WAYLAND_DISPLAY", None)
    if renderer == "lavapipe":
        os.environ.update({"LP_NUM_THREADS": "2", "LIBGL_ALWAYS_SOFTWARE": "1"})
    else:
        os.environ.pop("LP_NUM_THREADS", None)
        os.environ.pop("LIBGL_ALWAYS_SOFTWARE", None)
        os.environ["__GL_SHADER_DISK_CACHE_PATH"] = str(run / "tmp/nvidia-shader-cache")


def build_command(
    *,
    qemu: Path,
    run: Path,
    base: Path,
    ecid: int,
    accelerator: str,
    seconds: int,
    renderer: str,
    ssh_port: int | None,
    serial_socket: bool,
    network: bool = True,
    cpus: int = 1,
) -> list[str]:
    """Return the bounded QEMU command line for a disposable VMApple boot."""
    if type(cpus) is not int or not 1 <= cpus <= 8:
        raise ValueError("vCPU count must be an integer between 1 and 8")
    if serial_socket:
        serial = [
            "-chardev",
            f"socket,id=uart0,path={run}/serial.sock,server=on,wait=off,logfile={run}/serial.log",
            "-serial",
            "chardev:uart0",
        ]
    else:
        serial = ["-serial", f"file:{run}/serial.log"]

    machine = f"vmapple,accel={accelerator},uuid={ecid},graphics=off"
    graphics: list[str] = []
    if renderer != "none":
        machine = (
            f"vmapple,accel={accelerator},uuid={ecid},"
            "gfx-device=reims-vgpu-mmio,memory-backend=guestmem"
        )
        graphics = [
            "-object",
            f"memory-backend-file,id=guestmem,size={GUEST_RAM},share=on,"
            f"align={GUEST_RAM_ALIGNMENT},mem-path={run}/guest.ram",
            "-d",
            "guest_errors",
        ]

    cpu = "max" if accelerator == "tcg" else "host,pmu=off,kvm-psci-version=1.1"
    command = [
        "timeout",
        "--foreground",
        "--signal=TERM",
        "--kill-after=10s",
        f"{seconds}s",
        str(qemu),
        "-machine",
        machine,
        *graphics,
        "-cpu",
        cpu,
        "-smp",
        str(cpus),
        "-m",
        GUEST_RAM,
        "-display",
        "none",
        "-monitor",
        "none",
        *serial,
        "-qmp",
        f"unix:{run}/qmp.sock,server=on,wait=off",
        "-no-reboot",
        "-action",
        "panic=pause,shutdown=pause",
        "-bios",
        str(base / "AVPBooter.vmapple2.bin"),
        "-drive",
        f"if=pflash,format=raw,file.filename={run}/aux.img.trimmed,file.locking=off",
        "-drive",
        f"if=pflash,format=raw,file.filename={run}/disk.img,file.locking=off",
        "-drive",
        f"if=none,format=raw,file.filename={run}/aux.img.trimmed,file.locking=off,id=aux",
        "-device",
        "vmapple-virtio-blk-pci,variant=aux,drive=aux,share-rw=on",
        "-drive",
        f"if=none,format=raw,file.filename={run}/disk.img,file.locking=off,id=root",
        "-device",
        "vmapple-virtio-blk-pci,variant=root,drive=root,share-rw=on",
    ]
    if network:
        netdev = "user,id=net0,ipv6=off"
        if ssh_port is not None:
            netdev += f",hostfwd=tcp:127.0.0.1:{ssh_port}-:22"
        command += [
            "-netdev",
            netdev,
            "-device",
            "virtio-net-pci,netdev=net0,mac=52:54:00:76:61:70",
        ]
    else:
        command += ["-nic", "none"]
    return command
