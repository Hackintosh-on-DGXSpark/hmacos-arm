import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class ConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.module = importlib.import_module("hmacos_arm.config")
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()

    def test_paths_are_relocatable(self):
        with patch.dict(os.environ, {"HMACOS_ROOT": str(self.root)}, clear=True):
            paths = self.module.ProjectPaths.from_environment()
        self.assertEqual(paths.state, self.root / "artifacts")
        self.assertEqual(paths.runs, paths.state / "runs")
        self.assertEqual(paths.bundle, paths.state / "ventura-13.6-22G120")
        self.assertEqual(
            paths.qemu, paths.sysroot / "reims-vgpu/vendor/qemu/build/qemu-system-aarch64"
        )

    def test_current_run_pointer_roundtrip(self):
        with patch.dict(os.environ, {"HMACOS_ROOT": str(self.root)}, clear=True):
            paths = self.module.ProjectPaths.from_environment()
            run = paths.runs / "vm-1"
            run.mkdir(parents=True)
            self.assertIsNone(self.module.current_run(paths))
            self.module.record_launch(paths, run, 4321)
            self.assertEqual(self.module.current_run(paths), run)
            self.assertEqual((paths.state / "current.pid").read_text().strip(), "4321")
            self.module.clear_launch(paths)
            self.assertIsNone(self.module.current_run(paths))

    def test_state_and_tools_can_be_external(self):
        with patch.dict(
            os.environ,
            {
                "HMACOS_ROOT": str(self.root),
                "HMACOS_STATE_DIR": str(self.root / "state"),
                "HMACOS_SYSROOT": str(self.root / "deps"),
            },
            clear=True,
        ):
            paths = self.module.ProjectPaths.from_environment()
        self.assertEqual(paths.state, self.root / "state")
        self.assertEqual(paths.sysroot, self.root / "deps")

    def test_baseline_inode_and_symlinks_are_rejected(self):
        base, run = self.root / "base", self.root / "run"
        base.mkdir()
        run.mkdir()
        (base / "STAGING_COMPLETE").touch()
        for name in ("disk.img", "aux.img.trimmed"):
            (base / name).write_bytes(b"baseline")
            (run / name).write_bytes(b"copy")
        self.module.validate_run_storage(run, base)
        (run / "disk.img").unlink()
        os.link(base / "disk.img", run / "disk.img")
        with self.assertRaises(ValueError):
            self.module.validate_run_storage(run, base)
        (run / "disk.img").unlink()
        (run / "disk.img").symlink_to(base / "disk.img")
        with self.assertRaises(ValueError):
            self.module.validate_run_storage(run, base)

    def test_completion_marker_is_required(self):
        with self.assertRaises(ValueError):
            self.module.validate_run_storage(self.root, self.root / "missing")
