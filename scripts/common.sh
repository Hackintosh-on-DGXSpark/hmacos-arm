#!/usr/bin/env bash
# Sourced by native entry points. Build products live under build/, guest inputs
# under guest-image/, and each disposable VM under vm-instance/.
HMACOS_ROOT=${HMACOS_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)}
HMACOS_BUILD_DIR=${HMACOS_BUILD_DIR:-$HMACOS_ROOT/build}
HMACOS_GUEST_IMAGE_DIR=${HMACOS_GUEST_IMAGE_DIR:-$HMACOS_ROOT/guest-image}
HMACOS_BUNDLE=${HMACOS_BUNDLE:-$HMACOS_GUEST_IMAGE_DIR/ventura-13.6-22G120}
HMACOS_INSTANCE_DIR=${HMACOS_INSTANCE_DIR:-$HMACOS_ROOT/vm-instance}
HMACOS_QEMU=${HMACOS_QEMU:-$HMACOS_BUILD_DIR/qemu/qemu-system-aarch64}
export HMACOS_ROOT HMACOS_BUILD_DIR HMACOS_GUEST_IMAGE_DIR HMACOS_BUNDLE HMACOS_INSTANCE_DIR HMACOS_QEMU
export PYTHONPATH="$HMACOS_ROOT/src${PYTHONPATH:+:$PYTHONPATH}"
export PYTHONDONTWRITEBYTECODE=1

hmacos_tool() {
    command -v "$1" || { printf 'Missing tool: %s. See docs/build.md.\n' "$1" >&2; return 1; }
}

hmacos_require_host() {
    if [[ $(uname -s)/$(uname -m) != Linux/aarch64 || $(id -u) -eq 0 ]]; then
        printf 'Run this as the desktop user on the Arm Linux DGX, not the local Mac or root.\n' >&2
        return 2
    fi
}

# Prefer the project-local sysroot when present. It carries the DGX's private
# toolchain, headers, libraries, and pkg-config files; use it without installing
# anything system-wide.
hmacos_use_sysroot() {
    local sysroot=$HMACOS_ROOT/sysroot
    export PATH="$sysroot/build-venv/bin:$sysroot/usr/bin:$sysroot/cargo/bin:$sysroot/usr/lib/llvm-20/bin:$PATH"
    export PKG_CONFIG_PATH="$sysroot/usr/lib/aarch64-linux-gnu/pkgconfig:$sysroot/usr/share/pkgconfig"
    export PKG_CONFIG_LIBDIR="$sysroot/usr/lib/aarch64-linux-gnu/pkgconfig:$sysroot/usr/share/pkgconfig"
    export PKG_CONFIG_SYSROOT_DIR="$sysroot"
    export CFLAGS="-I$sysroot/usr/include -I$sysroot/usr/include/aarch64-linux-gnu${CFLAGS:+ $CFLAGS}"
    export CXXFLAGS="$CFLAGS"
    export LDFLAGS="-L$sysroot/usr/lib/aarch64-linux-gnu -Wl,-rpath,$sysroot/usr/lib/aarch64-linux-gnu${LDFLAGS:+ $LDFLAGS}"
    export RUSTUP_HOME="$sysroot/rustup"
    export CARGO_HOME="$sysroot/cargo"
}

# Re-run the calling script under process-scoped kvm group access when needed.
# Caller sets HMACOS_REEXEC_ARGV to the exact argv to replay.
hmacos_require_kvm() {
    if [[ ! -c /dev/kvm ]]; then
        printf '/dev/kvm is unavailable; enable a supported host KVM configuration first.\n' >&2
        return 1
    fi
    if [[ -r /dev/kvm && -w /dev/kvm ]]; then
        return 0
    fi
    if [[ $(id -gn) == kvm ]]; then
        printf 'KVM access is still unavailable in the kvm group; refusing repeated sudo attempts.\n' >&2
        return 1
    fi
    exec sudo -n -u "$(id -un)" -g kvm \
        env HMACOS_ROOT="$HMACOS_ROOT" HMACOS_BUILD_DIR="$HMACOS_BUILD_DIR" \
        HMACOS_GUEST_IMAGE_DIR="$HMACOS_GUEST_IMAGE_DIR" HMACOS_BUNDLE="$HMACOS_BUNDLE" \
        HMACOS_INSTANCE_DIR="$HMACOS_INSTANCE_DIR" HMACOS_QEMU="$HMACOS_QEMU" \
        "${HMACOS_REEXEC_ARGV[@]}"
}
