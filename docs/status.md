# Verified status

This project is research-quality and targets Ventura 13.6 (`22G120`) on the
arm64 NVIDIA DGX Spark. Results are not generalized to other macOS versions,
multi-vCPU guests, other Arm hosts, or production isolation.

| Capability | Evidence / limitation |
| --- | --- |
| Native KVM and 16 KiB guest pages | Bounded arithmetic, MMIO, PAC instruction and translation-table probes passed |
| Software desktop | Lavapipe desktop login and interaction confirmed by the user |
| Physical GB10 execution | Host Vulkan compute and imported-host-memory read/write passed |
| Guest Metal compute | Two 65,536-element readback checks passed; one deliberately wrong expected value produced one mismatch |
| Guest Vulkan enumeration | Vulkan Tools 1.3.280 + MoltenVK 1.2.8 produced summary/full reports, both exit 0 |
| Native screen | Launcher resolves the logged-in physical X11 session and opens Reims there |
| Optional Mac access | Authenticated RFB mirror of the same physical desktop verified over a loopback listener |
| Guest rendering quality | Artifacts, black frames, flicker, and texture-staging declines remain |
| Default Metal device | `MTLCreateSystemDefaultDevice()` can return nil; the probe uses explicit enumeration |
| Guest SSH | Not established as a supported access path |
| Wayland | Not supported by the current native launcher/sharing helpers |

The guest Vulkan device is **Apple Paravirtual device / MoltenVK**, not NVIDIA
GB10 directly. Host backend logs and a correct guest workload establish the
physical GPU path; successful enumeration or a working compositor alone does not.

Detailed dated evidence is in `docs/experiments/`. Those documents preserve
historical source paths and virtual-display experiments. Current instructions
are `README.md`, `docs/build.md`, and `docs/physical-desktop.md`.
