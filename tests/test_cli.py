import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class EntryPointTests(unittest.TestCase):
    def test_help_does_not_launch_workloads(self):
        for script in (
            "start_ventura_desktop.sh",
            "share_dgx_desktop.sh",
            "build_host.sh",
            "fetch_dependencies.sh",
            "setup_build_tools.sh",
            "doctor.sh",
        ):
            with self.subTest(script=script):
                result = subprocess.run(
                    ["bash", str(ROOT / "scripts" / script), "--help"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_invalid_limits_are_rejected_before_host_access(self):
        for script in ("start_ventura_desktop.sh", "share_dgx_desktop.sh"):
            for value in ("0", "59", "1801", "abc"):
                with self.subTest(script=script, value=value):
                    result = subprocess.run(
                        ["bash", str(ROOT / "scripts" / script), value],
                        capture_output=True,
                        text=True,
                        timeout=10,
                    )
                    self.assertEqual(result.returncode, 2)

    def test_source_path_traversal_is_rejected(self):
        result = subprocess.run(
            ["bash", str(ROOT / "scripts/start_ventura_desktop.sh"), "300", "../base"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("Invalid source-run", result.stderr)
