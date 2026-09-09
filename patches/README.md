# Patch set

`deps/sources.lock.json` is the authority for revisions, archive hashes, source
layout, and application order. Run `make fetch`; do not apply overlapping legacy
patches by hand. A second fetch checks that the same patches and Cargo lock are
already present rather than applying them twice. Unmanaged dependency directories
are never overwritten.

| Patch | Base and purpose |
| --- | --- |
| `reims-spark.patch` | Reims `2844274` plus QEMU fork `e17ddb98`: Linux arm64 VMApple/KVM support, 16 KiB shared page aliases, process-local logs, conservative CPU-renderer FP16 reporting, and the opt-in PAC-defaults research shim |
| `qemu-cargo-locked.patch` | Same QEMU fork: enforce the recorded Cargo dependency lock during the static-library build |
| `macosvm-capture.patch` | Optional Mac input-provisioning reference, `s-u/macosvm` tag `0.2-3`; not applied to the DGX build |

The main patch is applied at the Reims root after its QEMU source is populated
under `vendor/qemu`. Its local metal2vulkan path points to the separately pinned
sibling `sysroot/metal2vulkan`. It does not change the translator revision.

The guest kernel handoff is a separate, guarded runtime procedure in
`scripts/inject_ventura_kvm.gdb`, not an on-disk macOS modification. It updates CPU
timer metadata and the known GIC instruction sequence, refusing unknown inputs.
The PAC-defaults shim does not implement architectural key switching. These are
research constraints, not a production isolation guarantee.

## Licensing

These are modifications of upstream works, not a claim that the upstream code
is MIT licensed. QEMU retains its GPL and file-specific notices. The pinned
Reims repository includes an LGPL-3.0 license while its crate manifests declare
GPL-2.0-or-later; retain both sets of upstream notices. metal2vulkan declares
LGPL-3.0-or-later. Consult the exact upstream revisions before redistributing a
combined binary. This repository distributes patch text and original tooling,
not prebuilt QEMU/Reims binaries or Apple software. See `THIRD_PARTY.md`.
