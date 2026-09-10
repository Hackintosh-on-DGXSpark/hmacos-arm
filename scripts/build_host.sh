#!/usr/bin/env bash
# Build arm64 QEMU/Reims from the pinned submodules into build/.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"

if [[ ${1:-} == -h || ${1:-} == --help ]]; then
    cat <<'EOF'
Usage: bash scripts/build_host.sh

Requires initialized submodules (make submodules) and build dependencies from
scripts/install-deps.sh or HMACOS_SYSROOT. QEMU may fetch its pinned Meson
subprojects on the first build. Output goes to
build/qemu/qemu-system-aarch64; the Rust static library to build/rust/.
HMACOS_BUILD_JOBS sets parallelism (default 4).
EOF
    exit 0
fi
hmacos_require_host
[[ $# -eq 0 ]] || { printf 'No arguments expected.\n' >&2; exit 2; }
[[ -d $HMACOS_SYSROOT/usr ]] && hmacos_use_sysroot

jobs=${HMACOS_BUILD_JOBS:-4}
[[ $jobs =~ ^[1-8]$ ]] || { printf 'HMACOS_BUILD_JOBS must be 1..8.\n' >&2; exit 2; }
for tool in cc c++ pkg-config ninja meson cargo rustc; do hmacos_tool "$tool" >/dev/null; done

reims=$HMACOS_ROOT/deps/reims-vgpu
qemu_src=$reims/vendor/qemu
[[ -f $qemu_src/configure ]] || {
    printf 'Submodules are not initialized. Run: git submodule update --init --recursive\n' >&2
    exit 1
}
[[ -f $HMACOS_ROOT/deps/metal2vulkan/Cargo.toml ]] || {
    printf 'metal2vulkan submodule is missing.\n' >&2
    exit 1
}

build=$HMACOS_BUILD_DIR
mkdir -p "$build/qemu" "$build/rust" "$HMACOS_ROOT/logs"
exec 8>"$build/.build.lock"
flock -n 8 || { printf 'Another build is running.\n' >&2; exit 1; }

export CARGO_BUILD_JOBS="$jobs" REIMS_VGPU_BACKEND=vulkan
export REIMS_VGPU_TARGET_DIR="$build/rust"

printf 'Configuring QEMU (out-of-tree) ...\n'
(
    cd "$build/qemu"
    timeout --kill-after=10s 300s "$qemu_src/configure" \
        --target-list=aarch64-softmmu \
        --enable-kvm --enable-tcg --enable-slirp --enable-fdt \
        --disable-docs --disable-werror --disable-gtk --disable-sdl --disable-vnc \
        --disable-capstone --disable-rust --enable-download \
        --python="$(command -v python3)" -Dreims_vgpu_backend=vulkan
) >"$HMACOS_ROOT/logs/configure.log" 2>&1

printf 'Building; log: %s/logs/build.log\n' "$HMACOS_ROOT"
timeout --kill-after=15s 3600s ninja -C "$build/qemu" -j "$jobs" qemu-system-aarch64 \
    >"$HMACOS_ROOT/logs/build.log" 2>&1

"$HMACOS_QEMU" --version
sha256sum "$HMACOS_QEMU"
