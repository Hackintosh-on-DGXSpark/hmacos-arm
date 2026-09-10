"""Launch one bounded QEMU VMApple boot, hold the guarded handoff, record the result.

User-facing entry points live in `run/`; this module is the runtime library they
call. It never starts a virtual display or a persistent service.
"""

import argparse
import base64
import json
import os
import platform
import plistlib
import subprocess
import time

from .config import ProjectPaths, tool_environment, validate_run_storage
from .qemu import RENDERERS, build_command, prepare_render_environment

HANDOFF = "scripts/inject_ventura_kvm.gdb"
TIMEBASE_HZ = 1000000000
DEFAULT_BOOT_ARGS = "-v serial=11 debug=0x14c"


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_name")
    parser.add_argument("--accelerator", choices=("tcg", "kvm"), default="kvm")
    parser.add_argument("--seconds", type=int, default=300)
    parser.add_argument("--renderer", choices=RENDERERS, default="nvidia")
    parser.add_argument("--gdb-port", type=int)
    parser.add_argument("--ssh-port", type=int)
    parser.add_argument("--serial-socket", action="store_true")
    args = parser.parse_args()
    if platform.system() != "Linux" or platform.machine() != "aarch64":
        parser.error("run this on the Arm Linux DGX, not the local Mac")
    if os.geteuid() == 0:
        parser.error("run as the desktop user with process-scoped kvm group access, not root")
    if not args.run_name.replace("-", "").isalnum() or not 1 <= args.seconds <= 1800:
        parser.error("invalid run name or timeout (1..1800 seconds)")
    if args.gdb_port is not None and not 1024 <= args.gdb_port <= 65535:
        parser.error("GDB must use a nonprivileged loopback port")
    if args.ssh_port is not None and not 1024 <= args.ssh_port <= 65535:
        parser.error("SSH forwarding must use a nonprivileged loopback port")
    return args


def machine_ecid(base):
    config = json.loads((base / "vm.json").read_text())
    identity = plistlib.loads(base64.b64decode(config["machineId"], validate=True))
    ecid = identity["ECID"]
    if type(ecid) is not int or not 0 < ecid < 2**64:
        raise ValueError("invalid VM identity")
    return ecid


def run_handoff(paths, run, gdb_port):
    env = {
        **tool_environment(paths),
        "HMACOS_RUN_DIR": str(run),
        "HMACOS_TIMEBASE_HZ": str(TIMEBASE_HZ),
        "HMACOS_GDB_PORT": str(gdb_port),
        "HMACOS_BOOT_ARGS": DEFAULT_BOOT_ARGS,
    }
    with (run / "handoff.log").open("wb") as log:
        result = subprocess.run(
            [
                "timeout",
                "--kill-after=5s",
                "90s",
                "gdb",
                "-nx",
                "-q",
                "-batch",
                "-x",
                str(paths.root / HANDOFF),
            ],
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
            timeout=120,
        )
    if result.returncode != 0:
        raise RuntimeError(f"GDB handoff failed ({result.returncode}); see {run}/handoff.log")


def main():
    args = parse_args()
    os.umask(0o077)
    paths = ProjectPaths.from_environment()
    base, run = paths.bundle, paths.runs / args.run_name
    validate_run_storage(run, base)
    os.environ.update(tool_environment(paths))
    prepare_render_environment(run, args.renderer)

    command = build_command(
        qemu=paths.qemu,
        run=run,
        base=base,
        ecid=machine_ecid(base),
        accelerator=args.accelerator,
        seconds=args.seconds,
        renderer=args.renderer,
        gdb_port=args.gdb_port,
        ssh_port=args.ssh_port,
        serial_socket=args.serial_socket,
    )
    (run / "command.json").write_text(json.dumps(command, indent=2) + "\n")

    started = time.monotonic()
    with (run / "qemu.log").open("xb") as output:
        process = subprocess.Popen(command, cwd=run, stdout=output, stderr=subprocess.STDOUT)
        if args.gdb_port is not None:
            deadline = time.monotonic() + 30
            while not (run / "qmp.sock").exists():
                if process.poll() is not None:
                    raise RuntimeError(f"QEMU exited before handoff; see {run}/qemu.log")
                if time.monotonic() >= deadline:
                    process.terminate()
                    raise RuntimeError("QEMU did not create its QMP socket in time")
                time.sleep(0.1)
            run_handoff(paths, run, args.gdb_port)
            process.wait()
        else:
            process.wait()

    result = {
        "exit": process.returncode,
        "seconds": round(time.monotonic() - started, 2),
        "accelerator": args.accelerator,
        "pac_defaults_shim": bool(os.environ.get("QEMU_VMAPPLE_PAC_DEFAULTS")),
        "requested_renderer": args.renderer,
    }
    (run / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))
    print(f"Private boot evidence: {run}")


if __name__ == "__main__":
    main()
