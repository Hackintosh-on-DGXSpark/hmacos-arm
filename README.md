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
Apple firmware, disks, identities, credentials, and shader captures are not
included. Supply your own legitimately obtained matching inputs.

## Run the VM (day-to-day)

On the DGX's **physical desktop**, as the desktop user:

```sh
run/doctor.sh                                       # read-only host check
run/vm-up.sh 1800                                   # clean baseline
run/vm-up.sh 1800 <source-run>                      # keep installed guest tools
run/vm-up.sh 1800 "" --ssh-port 12222               # add a loopback SSH forward
run/vm-stop.sh                                      # stop the current VM
run/vm-status.sh                                    # show run, liveness, logs
```

`run/vm-up.sh` verifies the baseline, copies the disk and AUX into a new run
under `artifacts/runs/`, starts the guarded handoff, and opens the Reims window on
the physical screen. Keep its terminal open; Ctrl-C stops that VM. To retain a
guest change, pass the printed run name as `source-run` next time.

Optional viewing of that same physical screen from a Mac: `run/screen-share.sh`
(loopback VNC over SSH).

## Build the emulator (one-time)

```sh
make setup     # install the pinned Rust/Meson toolchain locally
make fetch     # hash-pinned sources + patches into sysroot/
make build     # arm64 QEMU/Reims Vulkan binary
```

Build output: `sysroot/reims-vgpu/vendor/qemu/build/qemu-system-aarch64`.
Sources and RPMs are pinned in `deps/` and `patches/`. Nothing is installed
system-wide; no driver, kernel, or service changes.

## Layout

| Path | Responsibility |
| --- | --- |
| `run/` | Operating the VM: `vm-up.sh`, `vm-stop.sh`, `vm-status.sh`, `screen-share.sh`, `doctor.sh` |
| `scripts/` | Engineering tooling: build/fetch/setup/probes, the GDB handoff, publication audit, `common.sh` |
| `src/hmacos_arm/` | Runtime library imported by `run/` scripts (see below) |
| `probes/` | Original host KVM/Vulkan and guest Metal correctness probes |
| `tools/guest-vulkan/` | Optional user-local `vulkaninfo` for the guest |
| `deps/` | Source revisions + SHA-256, toolchain versions, Cargo lock |
| `patches/` | Small, attributable upstream patch set and application notes |
| `tests/` | Synthetic unit tests and explicitly invoked host integration checks |
| `artifacts/`, `sysroot/` | Ignored private/generated state |

### `src/hmacos_arm/` modules

| Module | Used by | Responsibility |
| --- | --- | --- |
| `config.py` | everything | Relocatable paths (`HMACOS_*`), run pointers, baseline/run safety checks |
| `desktop.py` | `qemu`, `screen-share` | Resolve the active physical X11 session; refuse Wayland/SSH/virtual |
| `devicetree.py` | handoff | Guarded in-place CPU `timebase-frequency` update |
| `bundle.py` | `vm-up` | Verify the five input files against `SHA256SUMS` |
| `qemu.py` | `supervisor` | Build the QEMU argv and the renderer environment |
| `supervisor.py` | `vm-up` | Launch the bounded QEMU, run the handoff, record `result.json` |
| `sources.py` | `make fetch` | Download/verify/patch pinned dependencies (build-time) |
| `doctor.py` | `run/doctor.sh` | Read-only host prerequisite report |

Two lifecycles are deliberately separate: **building the emulator** (`make`,
`scripts/`, `deps/`, `patches/`) and **running a guest** (`run/`,
`src/hmacos_arm/`). Running never rebuilds; building never boots.

## Dependencies and when they are used

| Stage | Components |
| --- | --- |
| Provision inputs (optional, Mac) | `macosvm` (Apple VZ); Apple IPSW/firmware. Not distributed |
| Build emulator (DGX) | `reims-vgpu`, `qemu-reims-vgpu`, `metal2vulkan`, QEMU's `keycodemapdb`/SoftFloat/TestFloat, Rust 1.98.1, Meson/Ninja, Python build deps, host libs |
| Run VM (DGX) | Built `qemu-system-aarch64`, NVIDIA driver + Vulkan loader, physical X11, GDB (handoff), the 5 verified inputs |
| Guest tools (optional) | Vulkan-Headers/Loader/Tools 1.3.280, volk, MoltenVK 1.2.8 |
| Mac remote view (optional) | `x11vnc`/libvncserver, SSH, macOS Screen Sharing |
| Dev/CI | ruff, clang-format, GitHub Actions, GitLab CI |

Exact versions, revisions, and hashes: `deps/sources.lock.json`,
`deps/build-requirements.txt`, `deps/reims-Cargo.lock`,
`tools/guest-vulkan/sources.lock.json`. Licenses: [THIRD_PARTY.md](THIRD_PARTY.md).

## Testing

```sh
python3 -m venv .venv && .venv/bin/python -m pip install -r requirements-dev.txt
PATH="$PWD/.venv/bin:$PATH" make check
```

Unit/format checks need no GPU, Apple software, or network. Host probes are
separate, explicit experiments. CI never boots
a macOS guest.

Original tooling is [MIT licensed](LICENSE); upstream patches/dependencies retain
their licenses. See [security](SECURITY.md) before publishing or sharing.
