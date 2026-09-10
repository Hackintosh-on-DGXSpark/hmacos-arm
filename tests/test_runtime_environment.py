import argparse
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from hmacos_arm import qemu, supervisor
from hmacos_arm.config import ProjectPaths, runtime_environment


class RuntimeEnvironmentTests(unittest.TestCase):
    def test_new_checkout_can_reuse_an_external_toolchain(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "new-checkout"
            sysroot = Path(directory) / "shared-tools"
            executable = sysroot / "usr/lib/llvm-20/bin/llvm-dis"
            executable.parent.mkdir(parents=True)
            executable.write_text("#!/bin/sh\nexit 0\n")
            executable.chmod(0o700)
            with patch.dict(
                os.environ,
                {"HMACOS_ROOT": str(root), "HMACOS_SYSROOT": str(sysroot), "PATH": "/usr/bin"},
                clear=True,
            ):
                env = runtime_environment(ProjectPaths.from_environment())
                self.assertEqual(shutil.which("llvm-dis", path=env["PATH"]), str(executable))

    def test_runtime_environment_preserves_caller_settings(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.dict(
                os.environ,
                {"HMACOS_ROOT": str(root), "PATH": "/usr/bin:/bin", "LD_LIBRARY_PATH": "/custom"},
                clear=True,
            ):
                before = dict(os.environ)
                env = runtime_environment(ProjectPaths.from_environment())
                self.assertEqual(env["LD_LIBRARY_PATH"], "/custom")
                self.assertTrue(env["PATH"].endswith("/usr/bin:/bin"))
                self.assertEqual(dict(os.environ), before)

    def test_missing_shader_tool_is_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ, {"PATH": directory}, clear=True):
                with self.assertRaisesRegex(RuntimeError, "llvm-dis"):
                    qemu.check_shader_tools()

    def test_shader_tool_override_must_execute_successfully(self):
        with tempfile.TemporaryDirectory() as directory:
            broken = Path(directory) / "broken-llvm-dis"
            broken.write_text("#!/bin/sh\nprintf 'missing shared library' >&2\nexit 127\n")
            broken.chmod(0o700)
            with patch.dict(os.environ, {"METAL2VULKAN_LLVM_DIS": str(broken)}, clear=True):
                with self.assertRaisesRegex(RuntimeError, "missing shared library"):
                    qemu.check_shader_tools()

    def test_shader_tools_reach_the_qemu_child_from_a_plain_ssh_environment(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            instance = root / "instances/test"
            instance.mkdir(parents=True)
            llvm = root / "sysroot/usr/lib/llvm-20/bin"
            llvm.mkdir(parents=True)
            tools = root / "sysroot/usr/bin"
            tools.mkdir(parents=True)
            library = root / "sysroot/usr/lib/aarch64-linux-gnu"
            library.mkdir()
            for folder, name in ((llvm, "llvm-dis"), (tools, "spirv-val")):
                executable = folder / name
                executable.write_text(f"#!/bin/sh\nprintf 'fixture-{name}\\n'\n")
                executable.chmod(0o700)
            paths = ProjectPaths(
                root,
                root / "build",
                root / "images",
                root / "images/base",
                root / "instances",
                root / "build/qemu/qemu-system-aarch64",
            )
            args = argparse.Namespace(
                name="test",
                renderer="nvidia",
                accelerator="kvm",
                seconds=60,
                ssh_port=None,
                serial_socket=False,
                no_net=True,
            )
            # Model Reims spawning its shader helpers at runtime, not at build time.
            child = (
                "import os, subprocess; "
                "subprocess.run(['llvm-dis', '--version'], check=True); "
                "subprocess.run(['spirv-val', '--version'], check=True); "
                "print(os.environ.get('LD_LIBRARY_PATH', ''))"
            )
            old_umask = os.umask(0o077)
            try:
                with (
                    patch.dict(os.environ, {"PATH": "/usr/bin:/bin"}, clear=True),
                    patch.object(supervisor, "parse_args", return_value=args),
                    patch.object(ProjectPaths, "from_environment", return_value=paths),
                    patch.object(supervisor, "validate_instance_storage"),
                    patch.object(supervisor, "machine_ecid", return_value=12345),
                    patch.object(supervisor, "prepare_render_environment"),
                    patch.object(
                        supervisor, "build_command", return_value=[sys.executable, "-c", child]
                    ),
                ):
                    supervisor.main()
            finally:
                os.umask(old_umask)
            result = json.loads((instance / "result.json").read_text())
            self.assertEqual(result["exit"], 0, (instance / "qemu.log").read_text())
            output = (instance / "qemu.log").read_text()
            self.assertIn("fixture-llvm-dis", output)
            self.assertIn("fixture-spirv-val", output)
            self.assertIn(str(library), output)
            selected = json.loads((instance / "runtime-tools.json").read_text())
            self.assertEqual(selected["llvm-dis"]["path"], str(llvm / "llvm-dis"))
