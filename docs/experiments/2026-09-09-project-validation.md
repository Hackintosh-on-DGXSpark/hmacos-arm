# Project packaging and native validation

> Note: this report predates the later split of `scripts/` (build) from `run/`
> (operating the VM) and the `qemu.py`/`supervisor.py` split. Paths below reflect
> the layout at the time; current paths are in `README.md`.

## Scope

Converted the exploratory workspace into a relocatable source project. Runtime
Python is in `src/hmacos_arm/`, native entry points in `scripts/`, original
probes in `probes/`, and dependency provenance in `deps/` and `patches/`.
Retired the one-off compressed uploader, unverified guest-SSH bootstrap, and
duplicate PAC patch. Historical experiment reports remain available.

Native execution does not use VNC, Xvfb, or a second desktop. Optional Mac access
remains a separate authenticated mirror of the physical screen. No driver,
kernel, firmware, host security setting, or persistent group was changed.

## Build provenance

The working source revisions were confirmed from the original verified archives:
Reims `2844274c34baa1043d37995f5b1a9f1d265eae03`, QEMU fork
`e17ddb98f71df5697daf2f830587f672a8f4f5a7`, and metal2vulkan
`8b78eaca3be72b4e596aa1c790a4cd114ac1e9ec`. The newer Reims revision mentioned
in the initial research was not the source of the successful earlier build.

QEMU's keycodemapdb and Berkeley floating-point subprojects are now explicitly
pinned and populated, including the official Meson overlays. Python build
requirements and the Cargo lock are recorded. Cargo is invoked with `--locked`;
offline mode disables both source downloads and Cargo networking.

Native build command on the Spark:

```sh
HMACOS_ARCHIVE_CACHE=/home/spark/hmacos-arm/packages bash scripts/build_host.sh --offline
```

This used fresh dependency trees under `sysroot/reims-vgpu` and
`sysroot/metal2vulkan`, reusing the existing verified archive/crate caches and
private host development packages. The previous working build was left intact.
Missing subprojects, Python build dependencies, and private multiarch include/link
paths were identified and added to the reproducible setup rather than patched
around in the already-built binary.

Build result: QEMU 11.0.50, exit 0. New binary SHA-256:

```text
f47a8a051d03eeaa672434364d6237b41359b77abc91fec4b34896b4872fb832
```

## Checks

- `make check` passed locally and on the DGX: 20 synthetic tests, Ruff checks,
  Python formatting, C/Objective-C formatting, and shell syntax.
- Source preparation and patch checks passed twice, exercising the idempotent
  path. Unmanaged directories and malformed/checksum-invalid archives are refused.
- `make doctor` resolved the physical X11 session and NVIDIA GB10, with the
  newly built QEMU and the verified private bundle available.
- Native host probe compilation passed. Arithmetic/MMIO/PAC and 16 KiB/HVC KVM
  probes passed; the deliberately wrong oracle exited 1 as expected.
- NVIDIA Vulkan compute and imported-host-memory probes each verified all
  65,536 results. These host probes are not new guest Metal evidence.

Physical-screen VM validation:

```sh
bash scripts/start_ventura_desktop.sh 300 desktop-20260908-155305-178690
```

The run was `desktop-20260909-152627-56124`. All five baseline files verified;
the new in-project device-tree updater passed the real guarded GDB handoff for
one CPU, changing 24 MHz metadata to the host's 1 GHz timer frequency. Guest
serial output reached early boot completion, and Reims selected NVIDIA GB10.
The bounded QEMU run exited 124 after 302.57 seconds. No experimental VM or
virtual-display process remained afterward, and GB10 was idle.

This is a boot/tooling regression check, not a new graphics correctness or
performance study. Existing black-frame/flicker and default-device limitations
remain. Raw build, boot, and probe evidence stays in ignored local state; no
Apple input, identity, credential, or captured shader is published.
