"""Build the QEMU argv and graphics environment for one VMApple boot.

This module owns *what to run* only. Process lifecycle, the GDB handoff, and
result recording live in :mod:`hmacos_arm.supervisor`.
"""

import os
from pathlib import Path

from .desktop import physical_x11_environment

RENDERERS = ("none", "lavapipe", "nvidia")
GUEST_RAM = "8G"
GUEST_RAM_ALIGNMENT = 16384


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
    gdb_port: int | None,
    ssh_port: int | None,
    serial_socket: bool,
) -> list[str]:
    """Return the bounded QEMU command line for a disposable VMApple boot."""
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
        "1",
        "-m",
        GUEST_RAM,
        "-display",
        "none",
        "-monitor",
        "none",
        "-nic",
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
    if gdb_port is not None:
        command += ["-S", "-gdb", f"tcp:127.0.0.1:{gdb_port}"]
    if ssh_port is not None:
        network_index = command.index("-nic")
        del command[network_index : network_index + 2]
        command += [
            "-netdev",
            f"user,id=net0,restrict=on,ipv6=off,hostfwd=tcp:127.0.0.1:{ssh_port}-:22",
            "-device",
            "virtio-net-pci,netdev=net0,mac=52:54:00:76:61:70",
        ]
    return command
