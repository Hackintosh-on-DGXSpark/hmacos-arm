#!/usr/bin/env python3
"""Resolve the caller's active physical X11 desktop; never create a display."""

import os
import platform
import re
import subprocess
import sys


def physical_x11_environment():
    if platform.system() != "Linux":
        raise RuntimeError("Resolve the physical desktop on the Linux DGX host.")
    uid = os.getuid()
    session = subprocess.check_output(
        ["loginctl", "show-seat", "seat0", "-p", "ActiveSession", "--value"],
        text=True,
        timeout=10,
    ).strip()
    if not session.isalnum():
        raise RuntimeError("Log in to the physical desktop on seat0 first.")
    properties = dict(
        line.split("=", 1)
        for line in subprocess.check_output(
            [
                "loginctl",
                "show-session",
                session,
                "-p",
                "User",
                "-p",
                "Type",
                "-p",
                "Active",
                "-p",
                "Remote",
                "-p",
                "Seat",
            ],
            text=True,
            timeout=10,
        ).splitlines()
        if "=" in line
    )
    expected = {"User": str(uid), "Type": "x11", "Active": "yes", "Remote": "no", "Seat": "seat0"}
    if any(properties.get(key) != value for key, value in expected.items()):
        raise RuntimeError(
            "An active local X11 session on seat0 owned by this user is required; Wayland is not supported here."
        )

    runtime = f"/run/user/{uid}"
    bus_env = dict(
        os.environ, XDG_RUNTIME_DIR=runtime, DBUS_SESSION_BUS_ADDRESS=f"unix:path={runtime}/bus"
    )
    manager = dict(
        line.split("=", 1)
        for line in subprocess.check_output(
            ["systemctl", "--user", "show-environment"],
            env=bus_env,
            text=True,
            timeout=10,
        ).splitlines()
        if "=" in line
    )
    display = manager.get("DISPLAY", "")
    authority = manager.get("XAUTHORITY", "")
    if not re.fullmatch(r":\d+(?:\.\d+)?", display):
        raise RuntimeError(
            "The graphical session must provide a local X11 DISPLAY, not SSH X forwarding."
        )
    if (
        not os.path.isabs(authority)
        or "\n" in authority
        or "\r" in authority
        or not os.path.isfile(authority)
        or not os.access(authority, os.R_OK)
    ):
        raise RuntimeError(
            "The graphical session's XAUTHORITY file is not readable; log in to the physical desktop again."
        )
    result = {"DISPLAY": display, "XAUTHORITY": authority, "XDG_RUNTIME_DIR": runtime}
    outputs = subprocess.check_output(
        ["xrandr", "--query"],
        env=dict(os.environ, **result, LC_ALL="C"),
        text=True,
        timeout=10,
    )
    active = re.findall(
        r"^(\S+) connected (?:primary )?\d+x\d+[+-]\d+[+-]\d+", outputs, re.MULTILINE
    )
    if not any(
        not re.match(r"(?:VNC|XWAYLAND|DUMMY|screen|default)", name, re.IGNORECASE)
        for name in active
    ):
        raise RuntimeError(
            "An active physical RandR output is required; virtual displays are not used."
        )
    return result


if __name__ == "__main__":
    try:
        for key, value in physical_x11_environment().items():
            print(f"{key}={value}")
    except (RuntimeError, OSError, subprocess.SubprocessError) as error:
        print(f"Physical desktop unavailable: {error}", file=sys.stderr)
        sys.exit(1)
