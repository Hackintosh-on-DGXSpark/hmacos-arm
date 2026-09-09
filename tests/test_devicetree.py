import importlib
import struct
import unittest


def node(properties, children=()):
    result = struct.pack("<II", len(properties), len(children))
    for name, value in properties.items():
        result += name.encode().ljust(32, b"\0") + struct.pack("<I", len(value))
        result += value + b"\0" * (-len(value) % 4)
    return result + b"".join(children)


class DeviceTreeTests(unittest.TestCase):
    def setUp(self):
        self.patch_timebase = importlib.import_module("hmacos_arm.devicetree").patch_timebase

    def tree(self, second=24000000):
        cpus = node(
            {"name": b"cpus\0"},
            [
                node({"name": b"cpu0\0", "timebase-frequency": struct.pack("<I", 24000000)}),
                node({"name": b"cpu1\0", "timebase-frequency": struct.pack("<Q", second)}),
            ],
        )
        return bytearray(
            node({"name": b"root\0", "timebase-frequency": struct.pack("<I", 24000000)}, [cpus])
        )

    def test_only_cpu_timebases_change_without_resizing(self):
        tree = self.tree()
        size = len(tree)
        self.assertEqual(self.patch_timebase(tree, 1000000000), 2)
        self.assertEqual(len(tree), size)
        self.assertEqual(tree.count(struct.pack("<I", 24000000)), 1)
        self.assertEqual(tree.count(struct.pack("<I", 1000000000)), 2)

    def test_mismatch_is_atomic(self):
        tree = self.tree(second=42)
        before = bytes(tree)
        with self.assertRaises(ValueError):
            self.patch_timebase(tree, 1000000000)
        self.assertEqual(bytes(tree), before)

    def test_malformed_and_missing_cpus_are_rejected(self):
        for tree in (bytearray(b"short"), self.tree()[:-1], bytearray(node({"name": b"root\0"}))):
            with self.subTest(tree=tree[:8]), self.assertRaises(ValueError):
                self.patch_timebase(tree, 1000000000)
