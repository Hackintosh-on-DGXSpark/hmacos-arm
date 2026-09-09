# Testing and evidence

## Portable checks

`make check` runs synthetic unit tests, Python lint/format checks, C/Objective-C
format checks, and shell syntax checks. It requires no Apple inputs or GPU.
Tests cover physical-session selection, source/archive handling, bundle
validation, baseline inode protection, and atomic CPU device-tree updates.

## Native host probes

Build without running workloads:

```sh
make probes
```

On the DGX, run bounded KVM checks with process-scoped access:

```sh
sudo -n -u "$(id -un)" -g kvm timeout 10s build/probes/kvm-probe
sudo -n -u "$(id -un)" -g kvm timeout 10s build/probes/kvm-vmapple-probe
sudo -n -u "$(id -un)" -g kvm timeout 10s build/probes/kvm-negative
```

The negative control is expected to exit 1. A passing positive host probe is
not a macOS boot or GPU-acceleration result.

```sh
VK_DRIVER_FILES=/usr/share/vulkan/icd.d/nvidia_icd.json timeout 15s build/probes/vulkan-compute build/probes/compute.spv
VK_DRIVER_FILES=/usr/share/vulkan/icd.d/nvidia_icd.json timeout 15s build/probes/vulkan-host-import build/probes/compute.spv
```

These require physical GB10 and reject CPU fallback. Keep the existing driver,
kernel, and unrelated workloads intact. Do not run graphics tests in parallel
when interpreting timings.

## Guest checks

`probes/metal/metal_probe.m` is an arm64 macOS executable source. It refuses to
run on the physical Mac. Build it with legitimate Apple SDK tools for macOS 13,
ad-hoc sign it, and transfer it into the disposable guest. The tested command is
`metal-probe --explicit-device`; its `--negative-control` option deliberately
changes one expected value. See the dated GB10 Metal report for exact evidence.

The optional Vulkan installer under `tools/guest-vulkan/` uses a prepared offline
runtime archive containing Vulkan Tools/Loader 1.3.280 and MoltenVK 1.2.8. It
installs only under the guest user's `~/.local/` and checks both summary/full
enumeration. It does not install a macOS NVIDIA driver. See
`tools/guest-vulkan/README.md` for packaging and its limitations.

## Optional screen-sharing integration

Only when testing Mac access, with the physical desktop logged in and port 5900
unused:

```sh
PYTHONPATH=src python3 tests/integration/check_desktop_share.py
```

This explicitly starts a short-lived authenticated mirror, verifies the RFB
framebuffer dimensions, receives a small pixel sample without saving it, and
stops only its own server. It requires the host `cryptography` Python package.
It is not part of the default unit tests, native VM startup, or CI.

Record versions, commands, exit states, and limitations under `docs/experiments/`.
Keep all raw logs, screenshots, guest outputs, and VM identities in ignored
`artifacts/`. Do not call a visible desktop or enumeration alone a successful
hardware workload.
