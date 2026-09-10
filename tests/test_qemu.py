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
            run=Path("/instances/vm-1"),
            base=Path("/guest-image/ventura"),
            ecid=12345,
            accelerator="kvm",
            seconds=300,
            renderer="nvidia",
            ssh_port=None,
            serial_socket=True,
        )

    def test_headless_has_no_graphics_and_no_network_by_default(self):
        command = qemu.build_command(**{**self.kwargs, "renderer": "none", "network": False})
        self.assertIn("graphics=off", command[command.index("-machine") + 1])
        self.assertNotIn("-object", command)
        self.assertNotIn("-gdb", command)
        self.assertIn("-nic", command)

    def test_hardware_uses_reims_and_shared_16k_ram(self):
        command = qemu.build_command(**self.kwargs)
        machine = command[command.index("-machine") + 1]
        self.assertIn("gfx-device=reims-vgpu-mmio", machine)
        backend = command[command.index("-object") + 1]
        self.assertIn("share=on", backend)
        self.assertIn("align=16384", backend)
        self.assertEqual(
            command[command.index("-bios") + 1], "/guest-image/ventura/AVPBooter.vmapple2.bin"
        )

    def test_network_is_on_by_default_and_ssh_forward_is_optional(self):
        command = qemu.build_command(**self.kwargs)
        self.assertNotIn("-nic", command)
        self.assertEqual(command.count("-netdev"), 1)
        self.assertIn("user,id=net0", command[command.index("-netdev") + 1])
        forwarded = qemu.build_command(**{**self.kwargs, "ssh_port": 12222})
        self.assertIn("hostfwd=tcp:127.0.0.1:12222-:22", forwarded[forwarded.index("-netdev") + 1])

    def test_boot_args_are_deterministic(self):
        self.assertEqual(qemu.build_command(**self.kwargs), qemu.build_command(**self.kwargs))

    def test_eight_vcpus_are_forwarded_to_qemu(self):
        default = qemu.build_command(**self.kwargs)
        self.assertEqual(default[default.index("-smp") + 1], "1")
        command = qemu.build_command(**self.kwargs, cpus=8)
        self.assertEqual(command[command.index("-smp") + 1], "8")

    def test_vcpu_limits_are_enforced(self):
        for cpus in (0, -1, 9, "8", True):
            with self.subTest(cpus=cpus), self.assertRaisesRegex(ValueError, "vCPU"):
                qemu.build_command(**self.kwargs, cpus=cpus)


class RenderEnvironmentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.instance = Path(self.temp.name)

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
            qemu.prepare_render_environment(self.instance, "nvidia")
            self.assertEqual(
                os.environ["VK_DRIVER_FILES"], "/usr/share/vulkan/icd.d/nvidia_icd.json"
            )
            self.assertNotIn("LP_NUM_THREADS", os.environ)
            self.assertNotIn("WAYLAND_DISPLAY", os.environ)

    def test_none_is_a_noop(self):
        with patch.dict(os.environ, {"DISPLAY": ":9"}, clear=True):
            qemu.prepare_render_environment(self.instance, "none")
            self.assertEqual(os.environ["DISPLAY"], ":9")


if __name__ == "__main__":
    unittest.main()
