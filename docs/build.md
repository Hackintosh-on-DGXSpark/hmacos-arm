# Building on DGX Spark

The build is native Linux/aarch64. A Mac is not involved in building or running
QEMU/Reims. Optional preparation of Apple VM inputs and guest Metal binaries is
separate and requires legitimate Apple tooling.

## Native packages

Inspect the host first. On the supported Ubuntu 24.04 DGX image, the following
user-space development packages/tools are needed. Install missing packages only;
do not upgrade or replace the NVIDIA driver, kernel, firmware, or desktop stack.

```sh
sudo apt-get install --no-install-recommends \
  build-essential git curl python3-venv python3-dev pkg-config ninja-build \
  libglib2.0-dev libpixman-1-dev libfdt-dev libffi-dev zlib1g-dev \
  libgmp-dev nettle-dev libslirp-dev libvulkan-dev \
  libx11-dev libx11-xcb-dev libxkbcommon-dev libwayland-dev \
  gdb llvm-20 spirv-tools glslang-tools vulkan-tools x11-utils x11-xserver-utils
```

LLVM 20 must be available from a trusted repository for the host. This project
does not add package repositories automatically. `x11vnc` is optional and needed
only for Mac screen mirroring; `python3-cryptography` is optional for its integration
check. Neither is needed for native physical-screen VM use.

The existing development machine uses private extracted Ubuntu packages under
`sysroot/usr/`. Entry points support that layout without installing them globally.
If present, its binaries/libraries/pkg-config files are preferred for this
project only. Do not copy Linux binaries onto the Mac.

## Project-local build tools

```sh
make setup
```

This prepares `sysroot/build-venv/`, Meson 1.9.0, and Rust 1.98.1 under
`sysroot/{cargo,rustup}/`. It uses the official versioned rustup installer and
checks its checksum. Rust setup uses `--no-modify-path`. Existing matching tools
are reused; no system Rust installation or shell startup file is modified.

## Pinned sources and patches

```sh
make fetch
make build
```

`deps/sources.lock.json` pins Reims, the QEMU fork, metal2vulkan, and QEMU's
keycode/SoftFloat/TestFloat subprojects. This avoids relying on incomplete GitHub
QEMU archives or implicitly downloading arbitrary subproject revisions during
configure. The official QEMU Meson overlays for the floating-point libraries
are taken from the pinned QEMU tree.

`deps/reims-Cargo.lock` records the tested Rust dependencies. The build invokes
Cargo with `--locked`. Source archives are SHA-256 checked before extraction;
extraction uses Python's safe data filter. Existing unmanaged source directories
are refused, not deleted or overwritten. Existing prepared patches are checked
in reverse before being accepted on subsequent runs.

For a pre-populated archive cache:

```sh
export HMACOS_ARCHIVE_CACHE=/path/to/verified-archive-cache
bash scripts/build_host.sh --offline
```

The offline build also disables Cargo network access; its crate cache and Meson
environment must already be prepared. The development host's earlier cache is
`/home/spark/hmacos-arm/packages`, but new installations need not use that path.

The build defaults to four jobs; `HMACOS_BUILD_JOBS=1..8` is supported. Configure
has a 300-second bound and the build has an 1800-second bound. Resume a bounded
build by invoking it again; it does not discard build output. Logs are in
`logs/configure.log` and `logs/build.log`.

Output:

```text
sysroot/reims-vgpu/vendor/qemu/build/qemu-system-aarch64
```

The selected backend is Vulkan, stored as a Meson option. Reims owns the host
window. QEMU GTK, SDL, and VNC displays are disabled; optional host-screen
mirroring remains a separate program. No GUI server is started by the build.

System package versions are documented prerequisites, not a hermetic OS image.
The source and Cargo inputs are pinned; bit-identical binaries across compiler,
linker, OS package, and filesystem-path changes are not claimed.
