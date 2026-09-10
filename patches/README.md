# Patch archive

Historical record of the patch files used while the component changes were being
developed. They are **not applied by the build** any more: the live versions are
commits on the component forks, and `hmacos-arm` pins those forks as submodules.
Kept here for provenance and review.

| Patch | Earlier change | Now lives in |
| --- | --- | --- |
| `reims-spark.patch` | Reims + vendored QEMU Linux/aarch64 KVM support, 16 KiB page aliases, process-local logs, CPU-renderer FP16 | `reims-vgpu` `dgx-spark` (`101b604`) and `qemu-reims-vgpu` `dgx-spark` (`d8f185b`) |
| `qemu-cargo-locked.patch` | Build the Rust staticlib with `--locked` | `qemu-reims-vgpu` `dgx-spark` (`bcb0c54`) |
| `qemu-vmapple-pac-defaults.patch` | Earlier standalone PAC-defaults research shim | Folded into `reims-vgpu`/`qemu-reims-vgpu` `dgx-spark` |
| `reims-rust-linux-arm64.patch` | Earliest Rust Linux/aarch64 fix | Superseded by `reims-vgpu` `dgx-spark` |
| `reims-qemu-linux-arm64.patch` | Earliest QEMU Linux/aarch64 shim | Superseded by `qemu-reims-vgpu` `dgx-spark` |
| `macosvm-capture.patch` | Optional bounded GUI captures for provisioning | `macosvm` `dgx-spark` (`aa31623`) |

Fork repositories: <https://github.com/Hackintosh-on-DGXSpark>. Component
revisions are recorded in `.gitmodules`.

These patches are modifications of upstream works and retain the upstream
licenses (Reims LGPL/GPL, QEMU GPL, macosvm GPL). See `THIRD_PARTY.md`.
