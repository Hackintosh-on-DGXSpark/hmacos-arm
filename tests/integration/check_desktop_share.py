#!/usr/bin/env python3
"""Bounded real-host VNC authentication/framebuffer check; no pixels are saved."""

import json
import os
import re
import secrets
import signal
import socket
import struct
import subprocess
import tempfile
import time
from pathlib import Path

from hmacos_arm.config import ProjectPaths, tool_environment
from hmacos_arm.desktop import physical_x11_environment


def main():
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

    paths = ProjectPaths.from_environment()
    env = dict(tool_environment(paths), **physical_x11_environment())
    root = paths.root
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 5900))
    dimensions = re.search(
        r"current (\d+) x (\d+)",
        subprocess.check_output(["xrandr", "--query"], env=env, text=True, timeout=10),
    )
    assert dimensions is not None
    expected_size = tuple(map(int, dimensions.groups()))
    run = Path(tempfile.mkdtemp(prefix="desktop-share-check-", dir=paths.state))
    password_file = run / "vnc.passwd"
    password = secrets.token_hex(4)
    subprocess.run(
        ["x11vnc", "-storepasswd", str(password_file)],
        input=f"{password}\n{password}\ny\n".encode(),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=True,
        timeout=10,
    )
    os.chmod(password_file, 0o600)
    with (run / "server.log").open("w") as log:
        server = subprocess.Popen(
            ["bash", str(root / "scripts/share_dgx_desktop.sh"), "60", str(password_file)],
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        try:
            deadline = time.monotonic() + 15
            while True:
                assert server.poll() is None, f"sharing server exited; see {run}"
                try:
                    connection = socket.create_connection(("127.0.0.1", 5900), 2)
                    break
                except ConnectionRefusedError:
                    if time.monotonic() >= deadline:
                        raise TimeoutError("sharing server did not listen")
                    time.sleep(0.1)
            with connection:
                connection.settimeout(5)
                stream = connection.makefile("rb")
                assert stream.read(12).startswith(b"RFB ")
                connection.sendall(b"RFB 003.008\n")
                count = stream.read(1)[0]
                assert count > 0
                security = stream.read(count)
                assert 2 in security and 1 not in security, "VNC must require authentication"
                connection.sendall(b"\x02")
                challenge = stream.read(16)
                key = bytes(int(f"{byte:08b}"[::-1], 2) for byte in password.encode())
                cipher = Cipher(algorithms.TripleDES(key), modes.ECB()).encryptor()
                connection.sendall(cipher.update(challenge) + cipher.finalize())
                assert stream.read(4) == b"\0\0\0\0", "VNC authentication failed"
                connection.sendall(b"\x01")
                header = stream.read(24)
                size = struct.unpack("!HH", header[:4])
                assert size == expected_size, (size, expected_size)
                name_length = struct.unpack("!I", header[20:24])[0]
                assert name_length < 4096
                stream.read(name_length)
                connection.sendall(struct.pack("!BBHi", 2, 0, 1, 0))
                connection.sendall(struct.pack("!BBHHHH", 3, 0, 0, 0, 32, 32))
                assert stream.read(1) == b"\0"
                rectangles = struct.unpack("!BH", stream.read(3))[1]
                assert 0 < rectangles < 100
                pixels = 0
                regions = []
                for _ in range(rectangles):
                    x, y, width, height, encoding = struct.unpack("!HHHHi", stream.read(12))
                    regions.append((x, y, width, height, encoding))
                    assert encoding == 0 and x + width <= size[0] and y + height <= size[1]
                    length = width * height * (header[4] // 8)
                    assert len(stream.read(length)) == length
                    pixels += width * height
                # x11vnc may append software-cursor rectangles outside the requested patch.
                assert (0, 0, 32, 32, 0) in regions, (pixels, regions)
                print(
                    json.dumps(
                        {
                            "authentication": "required and passed",
                            "framebuffer": size,
                            "pixels_received_not_saved": pixels,
                            "logs": str(run),
                        }
                    )
                )
        finally:
            if server.poll() is None:
                os.killpg(server.pid, signal.SIGTERM)
                server.wait(timeout=10)
            password_file.unlink()


if __name__ == "__main__":
    main()
