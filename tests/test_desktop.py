import importlib
import importlib.util
import unittest
from contextlib import ExitStack
from unittest.mock import patch


class PhysicalDesktopTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(
            importlib.util.find_spec("hmacos_arm.desktop"), "physical desktop resolver missing"
        )
        self.module = importlib.import_module("hmacos_arm.desktop")
        self.session = "3"
        self.properties = "User=1000\nType=x11\nActive=yes\nRemote=no\nSeat=seat0\n"
        self.environment = (
            "DISPLAY=:1\nXAUTHORITY=/run/user/1000/gdm/Xauthority\nSECRET=not-exported\n"
        )
        self.outputs = "USB-C-2 connected primary 3840x2160+0+0 (normal)\n"
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(self.module.platform, "system", return_value="Linux"))
        self.stack.enter_context(patch.object(self.module.os, "getuid", return_value=1000))
        self.stack.enter_context(patch.object(self.module.os.path, "isfile", return_value=True))
        self.access = self.stack.enter_context(
            patch.object(self.module.os, "access", return_value=True)
        )
        self.stack.enter_context(
            patch.object(self.module.subprocess, "check_output", side_effect=self.command)
        )

    def command(self, args, **kwargs):
        self.assertEqual(kwargs["timeout"], 10)
        if args[:2] == ["loginctl", "show-seat"]:
            return self.session
        if args[:2] == ["loginctl", "show-session"]:
            return self.properties
        if args[:2] == ["systemctl", "--user"]:
            self.assertEqual(kwargs["env"]["XDG_RUNTIME_DIR"], "/run/user/1000")
            return self.environment
        if args[0] == "xrandr":
            self.assertEqual(kwargs["env"]["DISPLAY"], ":1")
            return self.outputs
        self.fail(f"unexpected command: {args}")

    def test_physical_session_overrides_stale_ssh_display(self):
        with patch.dict(self.module.os.environ, {"DISPLAY": ":99", "XAUTHORITY": "/tmp/old"}):
            self.assertEqual(
                self.module.physical_x11_environment(),
                {
                    "DISPLAY": ":1",
                    "XAUTHORITY": "/run/user/1000/gdm/Xauthority",
                    "XDG_RUNTIME_DIR": "/run/user/1000",
                },
            )

    def test_refuses_absent_or_unsuitable_session(self):
        self.session = ""
        with self.assertRaises(RuntimeError):
            self.module.physical_x11_environment()
        self.session = "3"
        for old, new in (
            ("1000", "1001"),
            ("x11", "wayland"),
            ("Active=yes", "Active=no"),
            ("Remote=no", "Remote=yes"),
            ("Seat=seat0", "Seat="),
        ):
            original = self.properties
            with self.subTest(new=new), self.assertRaises(RuntimeError):
                self.properties = original.replace(old, new)
                self.module.physical_x11_environment()
            self.properties = original

    def test_refuses_virtual_or_inactive_outputs(self):
        for output in (
            "VNC-0 connected 1600x900+0+0\n",
            "screen connected 1920x1080+0+0\n",
            "USB-C-2 disconnected\n",
            "USB-C-2 connected (normal)\n",
        ):
            with self.subTest(output=output), self.assertRaisesRegex(RuntimeError, "physical"):
                self.outputs = output
                self.module.physical_x11_environment()

    def test_refuses_remote_display_or_unreadable_auth(self):
        self.environment = "DISPLAY=localhost:10.0\nXAUTHORITY=/tmp/auth\n"
        with self.assertRaises(RuntimeError):
            self.module.physical_x11_environment()
        self.environment = "DISPLAY=:1\nXAUTHORITY=/tmp/auth\n"
        self.access.return_value = False
        with self.assertRaises(RuntimeError):
            self.module.physical_x11_environment()


if __name__ == "__main__":
    unittest.main()
