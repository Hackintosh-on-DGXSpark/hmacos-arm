# hmacos-arm

Research tooling for an **arm64 macOS Ventura guest on NVIDIA DGX Spark**, using
Linux KVM and the physical host GPU through Reims and Vulkan.

**Alpha, not a production hypervisor.** A guest Metal compute/readback probe has
passed two 65,536-element correctness runs and a one-error negative control on
GB10. Guest Vulkan enumeration also works through MoltenVK. Rendering artifacts,
black frames/flicker, incomplete Metal compatibility, and default-device lookup
failures remain. See [verified results](docs/status.md).

```text
Guest Metal -> AppleParavirtGPU -> Reims / metal2vulkan -> host Vulkan -> GB10
```

This reuses Reims; it is not PCI passthrough and does not install a macOS NVIDIA
driver. Apple firmware, disks, identities, credentials, and shader captures are
not included. Supply your own legitimately obtained matching inputs.

## Supported host

- NVIDIA DGX Spark / GB10, arm64 Ubuntu 24.04, Python 3.12 or newer.
- A working NVIDIA Vulkan driver and `/dev/kvm`. The recorded host used kernel
  `6.17.0-1026-nvidia` and driver `580.159.03`; no driver replacement is required.
- An active physical Xorg/X11 desktop owned by the invoking user on `seat0`.
- Ventura 13.6 (`22G120`) input bundle. One vCPU and 8 GiB RAM are used for the
  bounded guest; SMP and other guest releases are not claimed as supported.

No VNC server or virtual display is required to build or run the VM. Wayland is
not supported by the current display resolver; it fails rather than starting a
virtual fallback.

## Build on the DGX

Run commands in the checkout as the desktop user, not as root:

```sh
# Inspect/install the native user-space prerequisites listed in docs/build.md.
make setup
make fetch
make build
make doctor
```

`make setup` installs only project-local Rust/Meson tools. It does not install
system packages, kernels, drivers, services, or group membership. Sources and
build products go into ignored `sysroot/`. Revisions, archive checksums, Rust
version, Cargo lock, and patch order are pinned under `deps/` and `patches/`.
See [build details and offline use](docs/build.md).

## Supply the guest inputs

Prepare the matching disk, AUX/NVRAM, firmware, and identity as described in
[guest inputs](docs/inputs.md). The default private bundle directory is
`artifacts/ventura-13.6-22G120/`. It must have a verified `SHA256SUMS` manifest and
`STAGING_COMPLETE` marker. Do not point the launcher at your only working copy.

## Open the VM on the physical screen

```sh
bash scripts/start_ventura_desktop.sh 1800
```

The script discovers the logged-in physical desktop and opens a normal Reims
window there. It verifies the baseline, creates a disposable disk/AUX copy, uses
process-scoped `kvm` group access if needed, and performs the guarded GDB handoff.
It never changes `/dev/kvm` permissions or starts Xvfb/TigerVNC.

Each run prints its private directory. To retain installed tools or other guest
changes, pass a **stopped** prior run as the second argument:

```sh
bash scripts/start_ventura_desktop.sh 1800 desktop-20260908-155305-178690
```

That particular run is the development machine's installed-tools copy, not a
downloadable image. On a new host, use your own printed run name. The script
copies the source; it never boots the baseline or source inode in place.

Keep the launcher terminal open. Ctrl-C stops its VM; a 60..1800-second runtime
limit also applies. Disks remain for inspection. Subsequent runs start fresh
unless a source run is selected. Guest networking is off in the default launcher.

## Optional access from a local Mac

VNC is **only an optional mirror of the physical DGX screen** for remote use.
It is not part of VM graphics and creates no additional desktop. In a second
DGX terminal, start the bounded, password-protected mirror:

```sh
bash scripts/share_dgx_desktop.sh 1800
```

From the Mac, keep an SSH tunnel open, replacing `dgx-spark` with your SSH host:

```sh
ssh -N -o ExitOnForwardFailure=yes -L 127.0.0.1:15900:127.0.0.1:5900 dgx-spark
```

In another Mac terminal:

```sh
open vnc://127.0.0.1:15900
```

Use the separate VNC password selected on first use. This mirrors and controls
the whole physical host desktop. The server binds only to loopback, clipboard
sharing is off, and no persistent service is enabled. See
[physical desktop and remote access](docs/physical-desktop.md).

## Development and tests

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
PATH="$PWD/.venv/bin:$PATH" make check
```

Unit/format checks need no GPU, Apple software, VM credentials, or network after
development dependencies are installed. Host probes are separate, explicit
experiments: [testing guide](docs/testing.md). CI never boots a macOS guest.

| Path | Purpose |
| --- | --- |
| `src/hmacos_arm/` | Runtime configuration, physical desktop discovery, source preparation, boot and device-tree helpers |
| `scripts/` | Native DGX entry points, build tools, guarded GDB handoff |
| `deps/` | Source checksums, toolchain versions, Cargo dependency lock |
| `patches/` | Small, attributable upstream patch set and application notes |
| `probes/` | Host KVM/Vulkan and guest Metal correctness probes |
| `tools/guest-vulkan/` | Optional user-local guest Vulkan installer |
| `tests/` | Synthetic unit tests and explicitly invoked host integration checks |
| `docs/experiments/` | Dated results, commands, and limitations, not current setup instructions |
| `artifacts/`, `sysroot/` | Private/generated state; always ignored |

Runtime paths can be changed with `HMACOS_STATE_DIR`, `HMACOS_SYSROOT`,
`HMACOS_BUNDLE`, and an explicit `HMACOS_QEMU` override. Defaults are relative to
the checkout. The scripts do not depend on a particular login name or home path.

Original tooling is [MIT licensed](LICENSE). Upstream patches and dependencies
retain their licenses; read [third-party notices](THIRD_PARTY.md) before binary
redistribution. See [security and publication rules](SECURITY.md).
