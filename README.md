# hmacos-arm

Research tooling for an **arm64 macOS Ventura guest on NVIDIA DGX Spark**, using
Linux KVM and the physical host GPU through Reims and Vulkan.

**Alpha, not a production hypervisor.** A guest Metal compute/readback probe
passed two 65,536-element correctness runs and a one-error negative control on
GB10, and guest Vulkan enumeration works through MoltenVK. Rendering artifacts,
black frames/flicker, incomplete Metal compatibility, and default-device lookup
failures remain.

```text
Guest Metal -> AppleParavirtGPU -> Reims / metal2vulkan -> host Vulkan -> GB10
```

This reuses Reims; it is not PCI passthrough and installs no macOS NVIDIA driver.
Apple firmware, disks, identities, and credentials are not included. Supply your
own legitimately obtained matching inputs.

## Layout

```text
hmacos-arm/
├── deps/            component forks, pinned as git submodules
│   ├── reims-vgpu/       (nested vendor/qemu -> qemu-reims-vgpu)
│   ├── metal2vulkan/
│   └── macosvm/          (optional, input preparation only)
├── build/           all build products (ignored)
│   ├── qemu/            out-of-tree QEMU/Reims binary
│   └── rust/            reims-vgpu static library
├── guest-image/     shared read-only base image (ignored, private)
├── vm-instance/     one disposable copy/overlay per VM run (ignored)
├── run/             operating a VM: vm-up / vm-stop / vm-status / screen-share / doctor
├── scripts/         building: install-deps / build_host / build_probes / kvm handoff
├── src/hmacos_arm/  runtime library the run/ scripts call
├── in-guest-tools/  tools that run inside the guest (vulkan, metal-probe)
├── probes/          host KVM and Vulkan probes
└── tests/
```

Components live in their own repositories under the
[Hackintosh-on-DGXSpark](https://github.com/Hackintosh-on-DGXSpark) organization
and are pinned here as submodules, so their revisions are tracked without patch
files. `docs/` and `AGENTS.md` are local-only and not committed.

## Build (one-time, on the DGX)

```sh
make deps         # apt packages + official rustup (sudo; project dirs only)
make submodules   # fetch pinned component submodules
make build        # arm64 QEMU/Reims Vulkan binary into build/qemu/
make doctor       # read-only host check
```

`make deps` needs a non-root login with sudo. It does not replace the kernel,
driver, or firmware. Output: `build/qemu/qemu-system-aarch64`.

## Run a VM

Prepare a matching guest image (disk, AUX/NVRAM, firmware, identity) in
`guest-image/ventura-13.6-22G120/` with a verified `SHA256SUMS` and a
`STAGING_COMPLETE` marker, then on the physical desktop:

```sh
run/vm-up.sh 1800                        # new instance from the clean image
run/vm-up.sh 1800 <instance>             # copy a stopped instance (keeps tools)
run/vm-up.sh 1800 "" --ssh-port 12222    # forward a loopback port to guest SSH
run/vm-up.sh 1800 "" --no-net            # no network device (default is user-mode net)
run/vm-stop.sh
run/vm-status.sh
```

Each run gets its own `vm-instance/<name>/` (disposable disk + AUX copy, logs,
`result.json`). The image and any source instance are never booted in place.
Keep the `vm-up.sh` terminal open; Ctrl-C stops that instance.

Optional viewing of the same physical screen from a Mac: `run/screen-share.sh`
(loopback VNC over SSH).

## Guest tools (optional)

`in-guest-tools/vulkan/` installs a user-local `vulkaninfo` in the guest;
`in-guest-tools/metal-probe/` is the Metal correctness probe. Neither is needed
for the host GPU path.

## Testing

```sh
python3 -m venv .venv && .venv/bin/python -m pip install -r requirements-dev.txt
PATH="$PWD/.venv/bin:$PATH" make check
```

Unit/format checks need no GPU, Apple software, or network. Host probes are
explicit experiments (`make probes`). CI never boots a macOS guest.

Original tooling is [MIT licensed](LICENSE); component forks and dependencies
retain their upstream licenses, including Reims (LGPL/GPL) and QEMU (GPL). See
[THIRD_PARTY.md](THIRD_PARTY.md) and [SECURITY.md](SECURITY.md).
