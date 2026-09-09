# Optional guest Vulkan tools

These files run **inside the macOS guest**, not as part of DGX host startup.
They are not needed for Reims to use the host GPU. The installer uses no network,
root privileges, Homebrew, Xcode, or system-library replacement in the guest.

The tested offline payload contains:

```text
install.sh
vulkaninfo                  # copy of vulkaninfo.sh
vulkan-runtime.tar.gz
```

The archive has a single `1.3.280/` directory containing:

```text
libexec/vulkaninfo
lib/libvulkan.1.3.280.dylib
lib/libvulkan.1.dylib        # symlink to the versioned loader
lib/libvulkan.dylib         # symlink to the versioned loader
lib/libMoltenVK.dylib
share/vulkan/icd.d/MoltenVK_icd.json
licenses/
SHA256SUMS
```

Source versions and hashes are in `sources.lock.json`. Build Vulkan-Headers,
Vulkan-Loader, Volk, and Vulkan-Tools with CMake 3.29.6 and legitimate Apple SDK
tools, using `CMAKE_OSX_ARCHITECTURES=arm64` and
`CMAKE_OSX_DEPLOYMENT_TARGET=13.0`. In Vulkan-Tools disable `BUILD_CUBE`, `BUILD_ICD`,
and `BUILD_TESTS`; no mock ICD belongs in the payload. Use the arm64 slice of the
official MoltenVK 1.2.8 macOS library. Keep all upstream license files. Verify
Mach-O minimum OS versions and ad-hoc signatures after assembling the payload.

This preparation can be done in a macOS development environment; no Apple SDK
or prebuilt binary is redistributed in this repository. The DGX runtime remains
entirely host-native. The dated guest-vulkaninfo experiment describes the tested
preparation and transfer process; the payload is retained privately on the
development host, not downloadable from the source repositories.

Create `SHA256SUMS` within `1.3.280/` over the binaries, libraries, and ICD file,
then archive that directory preserving symlinks. Place the payload on a disposable
FAT USB image and attach it to the guest. Run in the guest Terminal:

```sh
/bin/sh /volumes/vktools/install.sh
cat /volumes/vktools/install.log
```

The installer verifies checksums and runs summary/full enumeration with separate
60-second bounds. Files are installed under `~/.local/share/hmacos-vulkan/1.3.280/`
and the wrapper under `~/.local/bin/vulkaninfo`. Existing differing files are not
overwritten. It does not modify your shell startup files:

```sh
~/.local/bin/vulkaninfo --summary
export PATH="$HOME/.local/bin:$PATH"  # optional for this terminal
```

Expected device: `Apple Paravirtual device`, driver `MoltenVK`, not GB10 directly.
Enumeration is not a rendering/compute correctness test. Black frames and flicker
remain possible; see `docs/status.md`.
