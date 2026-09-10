"""Launch one bounded QEMU VMApple instance, enable the firmware handoff, record the result.

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

from .config import ProjectPaths, validate_instance_storage
from .qemu import RENDERERS, build_command, prepare_render_environment

TIMEBASE_HZ = 1000000000
DEFAULT_BOOT_ARGS = "-v serial=11 debug=0x14c"


def handoff_environment(accelerator):
    """Environment that enables QEMU's built-in VMApple firmware handoff."""
    if accelerator != "kvm":
        return {}
    return {
        "QEMU_VMAPPLE_HANDOFF": "1",
        "QEMU_VMAPPLE_BOOT_ARGS": DEFAULT_BOOT_ARGS,
        "QEMU_VMAPPLE_TIMEBASE_HZ": str(TIMEBASE_HZ),
    }


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("name")
    parser.add_argument("--accelerator", choices=("tcg", "kvm"), default="kvm")
    parser.add_argument("--seconds", type=int, default=300)
    parser.add_argument("--renderer", choices=RENDERERS, default="nvidia")
    parser.add_argument("--ssh-port", type=int)
    parser.add_argument("--serial-socket", action="store_true")
    parser.add_argument("--no-net", action="store_true")
    args = parser.parse_args()
    if platform.system() != "Linux" or platform.machine() != "aarch64":
        parser.error("run this on the Arm Linux DGX, not the local Mac")
    if os.geteuid() == 0:
        parser.error("run as the desktop user with process-scoped kvm group access, not root")
    if not args.name.replace("-", "").isalnum() or not 1 <= args.seconds <= 1800:
        parser.error("invalid instance name or timeout (1..1800 seconds)")
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


def main():
    args = parse_args()
    os.umask(0o077)
    paths = ProjectPaths.from_environment()
    base, instance = paths.bundle, paths.instances / args.name
    validate_instance_storage(instance, base)
    prepare_render_environment(instance, args.renderer)
    os.environ.update(handoff_environment(args.accelerator))

    command = build_command(
        qemu=paths.qemu,
        run=instance,
        base=base,
        ecid=machine_ecid(base),
        accelerator=args.accelerator,
        seconds=args.seconds,
        renderer=args.renderer,
        ssh_port=args.ssh_port,
        serial_socket=args.serial_socket,
        network=not args.no_net,
    )
    (instance / "command.json").write_text(json.dumps(command, indent=2) + "\n")

    started = time.monotonic()
    with (instance / "qemu.log").open("xb") as output:
        process = subprocess.Popen(command, cwd=instance, stdout=output, stderr=subprocess.STDOUT)
        process.wait()

    result = {
        "exit": process.returncode,
        "seconds": round(time.monotonic() - started, 2),
        "accelerator": args.accelerator,
        "pac_defaults_shim": bool(os.environ.get("QEMU_VMAPPLE_PAC_DEFAULTS")),
        "requested_renderer": args.renderer,
    }
    (instance / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))
    print(f"Private instance evidence: {instance}")


if __name__ == "__main__":
    main()
