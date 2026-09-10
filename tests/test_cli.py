import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUN_SCRIPTS = ("vm-up.sh", "vm-stop.sh", "vm-status.sh", "screen-share.sh", "doctor.sh")
BUILD_SCRIPTS = ("build_host.sh", "install-deps.sh", "build_probes.sh")


class EntryPointTests(unittest.TestCase):
    def test_help_does_not_launch_workloads(self):
        for directory, scripts in (("run", RUN_SCRIPTS), ("scripts", BUILD_SCRIPTS)):
            for script in scripts:
                with self.subTest(script=f"{directory}/{script}"):
                    result = subprocess.run(
                        ["bash", str(ROOT / directory / script), "--help"],
                        capture_output=True,
                        text=True,
                        timeout=10,
                    )
                    self.assertEqual(result.returncode, 0, result.stderr)

    def test_invalid_limits_are_rejected_before_host_access(self):
        for script in ("vm-up.sh", "screen-share.sh"):
            for value in ("0", "59", "1801", "abc"):
                with self.subTest(script=script, value=value):
                    result = subprocess.run(
                        ["bash", str(ROOT / "run" / script), value],
                        capture_output=True,
                        text=True,
                        timeout=10,
                    )
                    self.assertEqual(result.returncode, 2)

    def test_source_path_traversal_is_rejected(self):
        result = subprocess.run(
            ["bash", str(ROOT / "run/vm-up.sh"), "300", "../image"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("Invalid source-instance", result.stderr)

    def test_invalid_ssh_port_is_rejected(self):
        result = subprocess.run(
            ["bash", str(ROOT / "run/vm-up.sh"), "300", "", "--ssh-port", "99999"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("Invalid --ssh-port", result.stderr)

    def test_invalid_vcpu_counts_are_rejected_before_host_access(self):
        for value in ("0", "9", "-1", "abc", ""):
            with self.subTest(value=value):
                command = ["bash", str(ROOT / "run/vm-up.sh"), "300", "", "--cpus"]
                if value:
                    command.append(value)
                result = subprocess.run(command, capture_output=True, text=True, timeout=10)
                self.assertEqual(result.returncode, 2)
                self.assertIn("Invalid --cpus", result.stderr)
