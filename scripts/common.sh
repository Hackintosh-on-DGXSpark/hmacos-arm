#!/usr/bin/env bash
# Sourced by native entry points; all generated state stays outside tracked code.
HMACOS_ROOT=${HMACOS_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)}
HMACOS_STATE_DIR=${HMACOS_STATE_DIR:-$HMACOS_ROOT/artifacts}
HMACOS_SYSROOT=${HMACOS_SYSROOT:-$HMACOS_ROOT/sysroot}
HMACOS_BUNDLE=${HMACOS_BUNDLE:-$HMACOS_STATE_DIR/ventura-13.6-22G120}
HMACOS_QEMU=${HMACOS_QEMU:-$HMACOS_SYSROOT/reims-vgpu/vendor/qemu/build/qemu-system-aarch64}
export HMACOS_ROOT HMACOS_STATE_DIR HMACOS_SYSROOT HMACOS_BUNDLE HMACOS_QEMU
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
