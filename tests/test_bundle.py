import hashlib
import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from hmacos_arm.bundle import FILES, verify_bundle


class BundleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.lines = []
        for name in sorted(FILES):
            data = f"synthetic fixture {name}".encode()
            (self.root / name).write_bytes(data)
            self.lines.append(f"{hashlib.sha256(data).hexdigest()}  {name}")
        (self.root / "SHA256SUMS").write_text("\n".join(self.lines) + "\n")

    def test_marks_only_after_all_hashes_pass(self):
        with redirect_stdout(io.StringIO()):
            verify_bundle(self.root)
            self.assertFalse((self.root / "STAGING_COMPLETE").exists())
            verify_bundle(self.root, mark=True)
        self.assertTrue((self.root / "STAGING_COMPLETE").is_file())

    def test_bad_hash_does_not_publish_marker(self):
        (self.root / "disk.img").write_bytes(b"changed")
        with redirect_stdout(io.StringIO()), self.assertRaises(ValueError):
            verify_bundle(self.root, mark=True)
        self.assertFalse((self.root / "STAGING_COMPLETE").exists())

    def test_manifest_cannot_escape_bundle(self):
        (self.root / "SHA256SUMS").write_text("a" * 64 + "  ../private\n")
        with self.assertRaises(ValueError):
            verify_bundle(self.root, mark=True)
