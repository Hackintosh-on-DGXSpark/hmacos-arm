#!/usr/bin/env python3
"""Bounded Linux VMApple boot using pre-created disposable raw storage copies."""

import argparse
import base64
import json
import os
import platform
import plistlib
import socket
import subprocess
import time

from .config import ProjectPaths, tool_environment, validate_run_storage
from .desktop import physical_x11_environment

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("run_name")
parser.add_argument("--accelerator", choices=("tcg", "kvm"), default="kvm")
parser.add_argument("--seconds", type=int, default=300)
parser.add_argument("--gdb-port", type=int)
parser.add_argument("--inspect-after", type=int)
parser.add_argument("--trace-aes", action="store_true")
parser.add_argument("--serial-socket", action="store_true")
renderers = parser.add_mutually_exclusive_group()
renderers.add_argument("--software-graphics", action="store_true")
renderers.add_argument(
    "--hardware-graphics",
    action="store_true",
    help="use the NVIDIA Vulkan ICD, with no software fallback",
)
parser.add_argument("--ssh-port", type=int)
args = parser.parse_args()
if platform.system() != "Linux" or platform.machine() != "aarch64":
    parser.error("run this on the Arm Linux Spark, not the local Mac")
if os.geteuid() == 0:
    parser.error("run as the desktop user with process-scoped kvm group access, not root")
if not args.run_name.replace("-", "").isalnum() or not 1 <= args.seconds <= 1800:
    parser.error("invalid run name or timeout (1..1800 seconds)")
if args.gdb_port is not None and not 1024 <= args.gdb_port <= 65535:
    parser.error("GDB must use a nonprivileged port")
if args.inspect_after is not None and not 1 <= args.inspect_after < args.seconds:
    parser.error("inspection must occur before the time limit")
if args.ssh_port is not None and not 1024 <= args.ssh_port <= 65535:
    parser.error("SSH forwarding must use a nonprivileged loopback port")
os.umask(0o077)
paths = ProjectPaths.from_environment()
root, base = paths.root, paths.bundle
run = paths.state / "linux-boots" / args.run_name
validate_run_storage(run, base)
os.environ.update(tool_environment(paths))
config = json.loads((base / "vm.json").read_text())
identity = plistlib.loads(base64.b64decode(config["machineId"], validate=True))
ecid = identity["ECID"]
if type(ecid) is not int or not 0 < ecid < 2**64:
    parser.error("invalid VM identity")
qemu = paths.qemu
machine = f"vmapple,accel={args.accelerator},uuid={ecid},graphics=off"
graphics = []
renderer = "nvidia" if args.hardware_graphics else "lavapipe" if args.software_graphics else "none"
if renderer != "none":
    os.environ.update(physical_x11_environment())
    machine = f"vmapple,accel={args.accelerator},uuid={ecid},gfx-device=reims-vgpu-mmio,memory-backend=guestmem"
    graphics = [
        "-object",
        f"memory-backend-file,id=guestmem,size=8G,share=on,align=16384,mem-path={run}/guest.ram",
        "-d",
        "guest_errors",
    ]
    (run / "tmp").mkdir(mode=0o700)
    os.environ.update(
        {
            "VK_DRIVER_FILES": f"/usr/share/vulkan/icd.d/{'nvidia' if args.hardware_graphics else 'lvp'}_icd.json",
            "WINIT_UNIX_BACKEND": "x11",
            "TMPDIR": str(run / "tmp"),
            "XDG_CACHE_HOME": str(run / "tmp/cache"),
            "MESA_SHADER_CACHE_DIR": str(run / "tmp/mesa-shader-cache"),
        }
    )
    if args.software_graphics:
        os.environ.update({"LP_NUM_THREADS": "2", "LIBGL_ALWAYS_SOFTWARE": "1"})
    else:
        os.environ.pop("LP_NUM_THREADS", None)
        os.environ.pop("LIBGL_ALWAYS_SOFTWARE", None)
        os.environ["__GL_SHADER_DISK_CACHE_PATH"] = str(run / "tmp/nvidia-shader-cache")
    os.environ.pop("WAYLAND_DISPLAY", None)
cpu = "max" if args.accelerator == "tcg" else "host,pmu=off,kvm-psci-version=1.1"
serial = ["-serial", f"file:{run}/serial.log"]
if args.serial_socket:
    serial = [
        "-chardev",
        f"socket,id=uart0,path={run}/serial.sock,server=on,wait=off,logfile={run}/serial.log",
        "-serial",
        "chardev:uart0",
    ]
command = [
    "timeout",
    "--foreground",
    "--signal=TERM",
    "--kill-after=10s",
    f"{args.seconds}s",
    str(qemu),
    "-machine",
    machine,
    *graphics,
    "-cpu",
    cpu,
    "-smp",
    "1",
    "-m",
    "8G",
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
if args.gdb_port is not None:
    command += ["-S", "-gdb", f"tcp:127.0.0.1:{args.gdb_port}"]
if args.ssh_port is not None:
    network_index = command.index("-nic")
    del command[network_index : network_index + 2]
    command += [
        "-netdev",
        f"user,id=net0,restrict=on,ipv6=off,hostfwd=tcp:127.0.0.1:{args.ssh_port}-:22",
        "-device",
        "virtio-net-pci,netdev=net0,mac=52:54:00:76:61:70",
    ]
if args.trace_aes:
    command += ["-d", "guest_errors,unimp"]
    for event in (
        "aes_fifo_process",
        "aes_cmd_flag",
        "aes_read",
        "aes_cmd_key_select_builtin",
        "aes_cmd_key_select_new",
        "aes_cmd_data",
    ):
        command += ["-trace", f"enable={event}"]
with (run / "command.json").open("x") as output:
    json.dump(command, output, indent=2)
started = time.monotonic()
with (run / "qemu.log").open("x") as output:
    process = subprocess.Popen(command, cwd=run, stdout=output, stderr=subprocess.STDOUT)
    if args.inspect_after is not None:
        try:
            process.wait(timeout=args.inspect_after)
        except subprocess.TimeoutExpired:
            with (run / "inspection.log").open("x") as inspection:
                try:
                    with socket.socket(socket.AF_UNIX) as connection:
                        connection.settimeout(120)
                        connection.connect(str(run / "qmp.sock"))
                        stream = connection.makefile("rwb", buffering=0)
                        json.loads(stream.readline())
                        requests = [
                            {"execute": "qmp_capabilities"},
                            {"execute": "query-status"},
                            {"execute": "stop"},
                            {
                                "execute": "human-monitor-command",
                                "arguments": {"command-line": "info registers"},
                            },
                            {
                                "execute": "pmemsave",
                                "arguments": {
                                    "val": 0x70000000,
                                    "size": 0x200000000,
                                    "filename": str(run / "ram.bin"),
                                },
                            },
                            {"execute": "cont"},
                        ]
                        was_running = False
                        for index, request in enumerate(requests):
                            if request["execute"] == "cont" and not was_running:
                                continue
                            request["id"] = index
                            stream.write(json.dumps(request).encode() + b"\n")
                            while True:
                                line = stream.readline()
                                if not line:
                                    raise RuntimeError("QMP closed during inspection")
                                response = json.loads(line)
                                if response.get("id") == index:
                                    print(json.dumps(response), file=inspection, flush=True)
                                    if "error" in response:
                                        raise RuntimeError(response["error"])
                                    if request["execute"] == "query-status":
                                        was_running = response["return"]["running"]
                                    break
                        if (run / "ram.bin").stat().st_size != 8 * 1024**3:
                            raise RuntimeError("guest RAM snapshot has the wrong size")
                except Exception as error:
                    print(f"Inspection failed: {error}", file=inspection, flush=True)
    process.wait()
result = {
    "exit": process.returncode,
    "seconds": round(time.monotonic() - started, 2),
    "accelerator": args.accelerator,
    "pac_defaults_shim": bool(os.environ.get("QEMU_VMAPPLE_PAC_DEFAULTS")),
    "requested_renderer": renderer,
}
(run / "result.json").write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps(result))
print(f"Private boot evidence: {run}")
