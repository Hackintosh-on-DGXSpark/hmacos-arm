# Ventura VMApple handoff: verbose arguments, timer metadata, and guarded GIC fix.
# GIC workaround follows steelbrain/experiment-macOS-arm64-on-asahi-linux-arm64.
python
import gdb
import json
import os
from pathlib import Path
import socket
import struct
import sys
import tempfile

run = Path(os.environ["HMACOS_RUN_DIR"])
frequency = int(os.environ["HMACOS_TIMEBASE_HZ"])
assert 0 < frequency <= 0xffffffff
arguments = os.environ.get("HMACOS_BOOT_ARGS", "-v serial=11 debug=0x14c").encode()
assert b"\0" not in arguments and len(arguments) < 608
gdb.execute("set architecture aarch64", to_string=True)
gdb.execute(f"target remote 127.0.0.1:{int(os.environ['HMACOS_GDB_PORT'])}", to_string=True)
bp = gdb.Breakpoint("*0xaca00000", type=gdb.BP_HARDWARE_BREAKPOINT, internal=True)
bp.ignore_count = 1
gdb.execute("continue", to_string=True)
assert int(gdb.parse_and_eval("$pc")) == 0xaca00000
inferior = gdb.selected_inferior()
boot = int(gdb.parse_and_eval("$x1"))
assert bytes(inferior.read_memory(boot, 4)) == struct.pack("<HH", 2, 2)
payload = (arguments + b"\0").ljust(608, b"\0")
inferior.write_memory(boot + 108, payload)
assert bytes(inferior.read_memory(boot + 108, 608)) == payload
virtual_base, physical_base = struct.unpack("<QQ", bytes(inferior.read_memory(boot + 8, 16)))
tree_virtual, tree_length = struct.unpack("<QI", bytes(inferior.read_memory(boot + 96, 12)))
assert tree_virtual >= virtual_base and 0 < tree_length < 4 * 1024 * 1024
tree_physical = tree_virtual - virtual_base + physical_base
tree = bytearray(inferior.read_memory(tree_physical, tree_length))
sys.path.insert(0, str(Path(os.environ["HMACOS_ROOT"]) / "src"))
from hmacos_arm.devicetree import patch_timebase
updated = patch_timebase(tree, frequency)
inferior.write_memory(tree_physical, tree)
assert bytes(inferior.read_memory(tree_physical, tree_length)) == tree
print(f"verified {updated} CPU timebase properties: 24000000 -> {frequency} Hz")

with socket.socket(socket.AF_UNIX) as connection:
    connection.settimeout(30)
    connection.connect(str(run / "qmp.sock"))
    stream = connection.makefile("rwb", buffering=0)
    json.loads(stream.readline())
    def qmp(command, args=None):
        request = {"execute": command}
        if args is not None:
            request["arguments"] = args
        stream.write(json.dumps(request).encode() + b"\n")
        while True:
            line = stream.readline()
            if not line:
                raise gdb.GdbError("QMP disconnected")
            response = json.loads(line)
            if "error" in response:
                raise gdb.GdbError(str(response["error"]))
            if "return" in response:
                return response["return"]
    qmp("qmp_capabilities")
    with tempfile.NamedTemporaryFile(dir=run, prefix="handoff-", suffix=".bin") as dump:
        qmp("pmemsave", {"val": physical_base, "size": 128 * 1024 * 1024, "filename": dump.name})
        window = Path(dump.name).read_bytes()
signature = struct.pack("<4I", 0x12afc009, 0xb8080d09, 0x52a10009, 0xb9008109)
assert window.count(signature) == 1, "unexpected GIC instruction sequence count"
address = physical_base + window.index(signature) + 4
for displacement, instruction in ((0, 0xb9008109), (8, 0xb9010109)):
    encoded = struct.pack("<I", instruction)
    inferior.write_memory(address + displacement, encoded)
    assert bytes(inferior.read_memory(address + displacement, 4)) == encoded
print("verified GIC MMIO workaround; no SIP/AMFI or PAC-enforcement changes")
bp.delete()
gdb.execute("detach", to_string=True)
end
