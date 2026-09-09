"""Read-only runtime prerequisite report for a physical DGX desktop."""

import argparse
import json
import os
import platform
import shutil
import subprocess

from .config import ProjectPaths, tool_environment
from .desktop import physical_x11_environment


def main():
    argparse.ArgumentParser(description=__doc__).parse_args()
    paths = ProjectPaths.from_environment()
    env = tool_environment(paths)
    report = {
        "host": f"{platform.system()}/{platform.machine()}",
        "root": str(paths.root),
        "state": str(paths.state),
        "qemu": str(paths.qemu),
        "qemu_built": paths.qemu.is_file(),
        "bundle_ready": (paths.bundle / "STAGING_COMPLETE").is_file(),
        "kvm_present": os.path.exists("/dev/kvm"),
        "kvm_direct_access": os.access("/dev/kvm", os.R_OK | os.W_OK),
    }
    missing = [
        name
        for name in (
            "timeout",
            "gdb",
            "sha256sum",
            "loginctl",
            "systemctl",
            "xrandr",
            "xdpyinfo",
            "nvidia-smi",
        )
        if shutil.which(name, path=env["PATH"]) is None
    ]
    report["missing_tools"] = missing
    try:
        report["desktop"] = physical_x11_environment()
        report["gpu"] = subprocess.check_output(
            [
                "nvidia-smi",
                "--query-gpu=name,driver_version,utilization.gpu",
                "--format=csv,noheader",
            ],
            env=env,
            text=True,
            timeout=10,
        ).strip()
    except (RuntimeError, OSError, subprocess.SubprocessError) as error:
        report["error"] = str(error)
    print(json.dumps(report, indent=2))
    return int(bool(missing or "error" in report or not report["kvm_present"]))


if __name__ == "__main__":
    raise SystemExit(main())
