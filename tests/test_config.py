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
        self.assertEqual(paths.build, self.root / "build")
        self.assertEqual(paths.guest_image, self.root / "guest-image")
        self.assertEqual(paths.bundle, paths.guest_image / "ventura-13.6-22G120")
        self.assertEqual(paths.instances, self.root / "vm-instance")
        self.assertEqual(paths.qemu, paths.build / "qemu/qemu-system-aarch64")

    def test_state_dirs_can_be_external(self):
        with patch.dict(
            os.environ,
            {
                "HMACOS_ROOT": str(self.root),
                "HMACOS_BUILD_DIR": str(self.root / "b"),
                "HMACOS_INSTANCE_DIR": str(self.root / "i"),
            },
            clear=True,
        ):
            paths = self.module.ProjectPaths.from_environment()
        self.assertEqual(paths.build, self.root / "b")
        self.assertEqual(paths.instances, self.root / "i")

    def test_current_instance_pointer_roundtrip(self):
        with patch.dict(os.environ, {"HMACOS_ROOT": str(self.root)}, clear=True):
            paths = self.module.ProjectPaths.from_environment()
            instance = paths.instances / "vm-1"
            instance.mkdir(parents=True)
            self.assertIsNone(self.module.current_instance(paths))
            self.module.record_instance(paths, instance, 4321)
            self.assertEqual(self.module.current_instance(paths), instance)
            self.module.clear_instance(paths)
            self.assertIsNone(self.module.current_instance(paths))

    def test_guest_image_inode_and_symlinks_are_rejected(self):
        base, instance = self.root / "image", self.root / "inst"
        base.mkdir()
        instance.mkdir()
        (base / "STAGING_COMPLETE").touch()
        for name in ("disk.img", "aux.img.trimmed"):
            (base / name).write_bytes(b"image")
            (instance / name).write_bytes(b"copy")
        self.module.validate_instance_storage(instance, base)
        (instance / "disk.img").unlink()
        os.link(base / "disk.img", instance / "disk.img")
        with self.assertRaises(ValueError):
            self.module.validate_instance_storage(instance, base)
        (instance / "disk.img").unlink()
        (instance / "disk.img").symlink_to(base / "disk.img")
        with self.assertRaises(ValueError):
            self.module.validate_instance_storage(instance, base)

    def test_marker_is_required(self):
        with self.assertRaises(ValueError):
            self.module.validate_instance_storage(self.root, self.root / "missing")
