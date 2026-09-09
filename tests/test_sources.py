import hashlib
import io
import tarfile
import tempfile
import unittest
from pathlib import Path

from hmacos_arm.sources import fetch_source


class SourceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.source = {
            "destination": "dependency",
            "revision": "a" * 40,
            "prefix": "upstream",
            "archive": "source.tar.gz",
        }

    def archive(self, name="upstream/code.txt"):
        archive = self.root / "source.tar.gz"
        with tarfile.open(archive, "w:gz") as output:
            member = tarfile.TarInfo(name)
            member.size = 4
            output.addfile(member, io.BytesIO(b"code"))
        self.source["sha256"] = hashlib.sha256(archive.read_bytes()).hexdigest()

    def test_idempotent_and_preserves_existing_edits(self):
        self.archive()
        directory = fetch_source(self.source, self.root, self.root, offline=True)
        (directory / "code.txt").write_text("operator edit")
        fetch_source(self.source, self.root, self.root, offline=True)
        self.assertEqual((directory / "code.txt").read_text(), "operator edit")

    def test_hash_mismatch_and_archive_escape_fail(self):
        self.archive()
        self.source["sha256"] = "0" * 64
        with self.assertRaises(ValueError):
            fetch_source(self.source, self.root, self.root, offline=True)
        self.archive("../escape")
        with self.assertRaises(ValueError):
            fetch_source(self.source, self.root, self.root, offline=True)
        self.assertFalse((self.root / "dependency").exists())

    def test_unmanaged_destination_is_not_overwritten(self):
        self.archive()
        target = self.root / "dependency"
        target.mkdir()
        (target / "mine").touch()
        with self.assertRaises(ValueError):
            fetch_source(self.source, self.root, self.root, offline=True)
        self.assertTrue((target / "mine").exists())
