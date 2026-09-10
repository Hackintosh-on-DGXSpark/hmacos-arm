#!/usr/bin/env bash
# Sourced by native entry points; all generated state stays outside tracked code.
HMACOS_ROOT=${HMACOS_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)}
HMACOS_STATE_DIR=${HMACOS_STATE_DIR:-$HMACOS_ROOT/artifacts}
HMACOS_SYSROOT=${HMACOS_SYSROOT:-$HMACOS_ROOT/sysroot}
HMACOS_BUNDLE=${HMACOS_BUNDLE:-$HMACOS_STATE_DIR/ventura-13.6-22G120}
HMACOS_RUNS_DIR=${HMACOS_RUNS_DIR:-$HMACOS_STATE_DIR/runs}
HMACOS_QEMU=${HMACOS_QEMU:-$HMACOS_SYSROOT/reims-vgpu/vendor/qemu/build/qemu-system-aarch64}
export HMACOS_ROOT HMACOS_STATE_DIR HMACOS_SYSROOT HMACOS_BUNDLE HMACOS_RUNS_DIR HMACOS_QEMU
export PYTHONPATH="$HMACOS_ROOT/src${PYTHONPATH:+:$PYTHONPATH}"
export PYTHONDONTWRITEBYTECODE=1
export RUSTUP_HOME="${RUSTUP_HOME:-$HMACOS_SYSROOT/rustup}"
export CARGO_HOME="${CARGO_HOME:-$HMACOS_SYSROOT/cargo}"
export PATH="$HMACOS_SYSROOT/usr/lib/llvm-20/bin:/usr/lib/llvm-20/bin:$HMACOS_SYSROOT/usr/bin:$HMACOS_SYSROOT/build-venv/bin:$HMACOS_SYSROOT/cargo/bin:$PATH"
if [[ -d $HMACOS_SYSROOT/usr/lib/aarch64-linux-gnu ]]; then
    export LD_LIBRARY_PATH="$HMACOS_SYSROOT/usr/lib/aarch64-linux-gnu${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
fi

hmacos_tool() {
    command -v "$1" || { printf 'Missing tool: %s. See docs/build.md.\n' "$1" >&2; return 1; }
}

hmacos_require_host() {
    if [[ $(uname -s)/$(uname -m) != Linux/aarch64 || $(id -u) -eq 0 ]]; then
        printf 'Run this as the desktop user on the Arm Linux DGX, not the local Mac or root.\n' >&2
        return 2
    fi
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
        env HMACOS_ROOT="$HMACOS_ROOT" HMACOS_STATE_DIR="$HMACOS_STATE_DIR" \
        HMACOS_SYSROOT="$HMACOS_SYSROOT" HMACOS_BUNDLE="$HMACOS_BUNDLE" \
        HMACOS_RUNS_DIR="$HMACOS_RUNS_DIR" HMACOS_QEMU="$HMACOS_QEMU" \
        "${HMACOS_REEXEC_ARGV[@]}"
}
