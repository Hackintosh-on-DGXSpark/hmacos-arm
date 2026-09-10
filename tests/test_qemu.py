import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from hmacos_arm import qemu


class BuildCommandTests(unittest.TestCase):
    def setUp(self):
        self.kwargs = dict(
            qemu=Path("/opt/qemu-system-aarch64"),
            run=Path("/state/runs/vm-1"),
            base=Path("/state/base"),
            ecid=12345,
            accelerator="kvm",
            seconds=300,
            renderer="nvidia",
            gdb_port=19001,
            ssh_port=None,
            serial_socket=True,
        )

    def test_headless_has_no_graphics_object(self):
        command = qemu.build_command(**{**self.kwargs, "renderer": "none", "gdb_port": None})
        self.assertIn("graphics=off", command[command.index("-machine") + 1])
        self.assertNotIn("-object", command)
        self.assertNotIn("-gdb", command)

    def test_hardware_uses_reims_and_shared_16k_ram(self):
        command = qemu.build_command(**self.kwargs)
        machine = command[command.index("-machine") + 1]
        self.assertIn("gfx-device=reims-vgpu-mmio", machine)
        backend = command[command.index("-object") + 1]
        self.assertIn("share=on", backend)
        self.assertIn("align=16384", backend)
        self.assertEqual(command[command.index("-bios") + 1], "/state/base/AVPBooter.vmapple2.bin")
        self.assertIn("-gdb", command)

    def test_ssh_port_replaces_the_disabled_nic_once(self):
        command = qemu.build_command(**{**self.kwargs, "ssh_port": 12222})
        self.assertEqual(command.count("-netdev"), 1)
        self.assertNotIn("-nic", command)
        self.assertIn("hostfwd=tcp:127.0.0.1:12222-:22", command[command.index("-netdev") + 1])

    def test_boot_args_are_deterministic(self):
        self.assertEqual(qemu.build_command(**self.kwargs), qemu.build_command(**self.kwargs))


class RenderEnvironmentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.run = Path(self.temp.name)

    def test_nvidia_selects_the_physical_session_and_no_software_fallback(self):
        with (
            patch.object(
                qemu,
                "physical_x11_environment",
                return_value={"DISPLAY": ":1", "XAUTHORITY": "/auth", "XDG_RUNTIME_DIR": "/run/u"},
            ),
            patch.dict(
                os.environ,
                {
                    "LP_NUM_THREADS": "2",
                    "LIBGL_ALWAYS_SOFTWARE": "1",
                    "WAYLAND_DISPLAY": "wayland-0",
                },
                clear=True,
            ),
        ):
            qemu.prepare_render_environment(self.run, "nvidia")
            self.assertEqual(
                os.environ["VK_DRIVER_FILES"], "/usr/share/vulkan/icd.d/nvidia_icd.json"
            )
            self.assertEqual(os.environ["DISPLAY"], ":1")
            self.assertNotIn("LP_NUM_THREADS", os.environ)
            self.assertNotIn("WAYLAND_DISPLAY", os.environ)

    def test_none_is_a_noop(self):
        with patch.dict(os.environ, {"DISPLAY": ":9"}, clear=True):
            qemu.prepare_render_environment(self.run, "none")
            self.assertEqual(os.environ["DISPLAY"], ":9")


if __name__ == "__main__":
    unittest.main()
