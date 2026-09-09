#!/usr/bin/env bash
# Build only in the project sysroot. Never install a kernel, driver, or service.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"
trap 'status=$?; printf "Build failed; inspect %s/logs/configure.log and build.log\n" "$HMACOS_ROOT" >&2; exit "$status"' ERR
if [[ ${1:-} == --help ]]; then
    printf 'Usage: bash scripts/build_host.sh [--offline]\n'
    printf 'Prepare pinned sources and build arm64 QEMU/Reims on the DGX. HMACOS_BUILD_JOBS defaults to 4.\n'
    exit 0
fi
if [[ $(uname -s)/$(uname -m) != Linux/aarch64 || $(id -u) -eq 0 ]]; then
    printf 'Build as a non-root user on the Arm Linux DGX.\n' >&2
    exit 2
fi
jobs=${HMACOS_BUILD_JOBS:-4}
[[ $jobs =~ ^[1-8]$ ]] || { printf 'HMACOS_BUILD_JOBS must be 1..8.\n' >&2; exit 2; }
if [[ ${1:-} == --offline ]]; then export CARGO_NET_OFFLINE=true; fi
python3 -m hmacos_arm.sources "$@"
rust=$(python3 -c 'import json,os; print(json.load(open(os.environ["HMACOS_ROOT"]+"/deps/sources.lock.json"))["toolchain"]["rust"])')
[[ $(rustc --version) == "rustc $rust "* ]] || { printf 'Expected Rust %s; see docs/build.md.\n' "$rust" >&2; exit 1; }
for tool in cc c++ pkg-config ninja meson; do hmacos_tool "$tool" >/dev/null; done
export CARGO_BUILD_JOBS="$jobs" REIMS_VGPU_BACKEND=vulkan
extra_config=()
if [[ -d $HMACOS_SYSROOT/usr/lib/aarch64-linux-gnu/pkgconfig ]]; then
    export PKG_CONFIG_SYSROOT_DIR="$HMACOS_SYSROOT"
    export PKG_CONFIG_PATH="$HMACOS_SYSROOT/usr/lib/aarch64-linux-gnu/pkgconfig${PKG_CONFIG_PATH:+:$PKG_CONFIG_PATH}"
    extra_config+=("--extra-cflags=-I$HMACOS_SYSROOT/usr/include -I$HMACOS_SYSROOT/usr/include/aarch64-linux-gnu")
    extra_config+=("--extra-ldflags=-L$HMACOS_SYSROOT/usr/lib/aarch64-linux-gnu -Wl,-rpath,$HMACOS_SYSROOT/usr/lib/aarch64-linux-gnu")
fi
tree=$HMACOS_SYSROOT/reims-vgpu
build=$tree/vendor/qemu/build
mkdir -p "$HMACOS_ROOT/logs" "$build"
exec 8>"$HMACOS_SYSROOT/build.lock"
flock -n 8 || { printf 'Another dependency build is running.\n' >&2; exit 1; }
(
    cd "$build"
    timeout --kill-after=10s 300s ../configure --target-list=aarch64-softmmu \
        --enable-kvm --enable-tcg --enable-slirp --enable-fdt \
        --disable-docs --disable-werror --disable-gtk --disable-sdl --disable-vnc \
        --disable-capstone --disable-rust --disable-download \
        --python="$(command -v python3)" -Dreims_vgpu_backend=vulkan "${extra_config[@]}"
) >"$HMACOS_ROOT/logs/configure.log" 2>&1
meson configure "$build" -Dreims_vgpu_backend=vulkan
printf 'Building QEMU/Reims; log: %s/logs/build.log\n' "$HMACOS_ROOT"
timeout --kill-after=15s 1800s ninja -C "$build" -j "$jobs" qemu-system-aarch64 \
    >"$HMACOS_ROOT/logs/build.log" 2>&1
"$build/qemu-system-aarch64" --version
sha256sum "$build/qemu-system-aarch64"
