# Third-party provenance

The root MIT license covers original project tooling and documentation only.
Dependencies are downloaded into ignored `sysroot/`, not copied into this Git
repository. Their own licenses, copyright notices, and redistribution obligations
continue to apply. The version and hash authority is `deps/sources.lock.json`.

| Component | Source / applicable notices |
| --- | --- |
| Reims vGPU | https://github.com/steelbrain/reims-vgpu at `2844274c34baa1043d37995f5b1a9f1d265eae03`; repository LGPL-3.0 text and GPL-2.0-or-later crate metadata are both retained |
| QEMU Reims fork | https://github.com/steelbrain/qemu-reims-vgpu at `e17ddb98f71df5697daf2f830587f672a8f4f5a7`; GPL-2.0 and file-specific notices |
| metal2vulkan | https://github.com/steelbrain/metal2vulkan at `8b78eaca3be72b4e596aa1c790a4cd114ac1e9ec`; LGPL-3.0-or-later |
| keycodemapdb | QEMU project; upstream `LICENSE.*` notices and the revision pinned by QEMU's wrap file |
| Berkeley SoftFloat/TestFloat | QEMU mirrors of John Hauser's libraries; BSD-3-Clause and included notices |
| Rust crates | Registry checksums and versions in `deps/reims-Cargo.lock`; each crate retains its license |
| macosvm | https://github.com/s-u/macosvm, tag `0.2-3`; copyright Simon Urbanek, GPL version 2 or (at the user's option) version 3, applies to the optional capture patch |
| Vulkan Headers/Loader/Tools | Khronos Group, Vulkan SDK `1.3.280`; Apache-2.0 and included notices |
| MoltenVK | Khronos Group, `v1.2.8`; Apache-2.0 and included notices |
| volk | `01986ac85fa2e5c70df09aeae9c907e27c5d50b2`; MIT |
| x11vnc / LibVNCServer | Optional screen-sharing tools supplied by the host or a private sysroot; upstream GPL notices apply |

The Apple boot-info layout, device-tree timebase handling, and firmware entry
point were studied using the public
[Asahi macOS experiment](https://github.com/steelbrain/experiment-macOS-arm64-on-asahi-linux-arm64)
and QEMU research helpers. The in-QEMU firmware handoff does not embed Apple
device-tree dumps or code.

Apple firmware, IPSWs, VM disks, AUX/NVRAM, machine identities, credentials,
captured Metal libraries/AIR, and guest screenshots are not distributed. Users
must obtain their own matching inputs legitimately and comply with applicable
software licenses. This project is independent of Apple and NVIDIA.
