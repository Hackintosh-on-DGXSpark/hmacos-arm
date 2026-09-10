#!/usr/bin/env bash
# Install the system-wide build dependencies for hmacos-arm on the DGX.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"

if [[ ${1:-} == -h || ${1:-} == --help ]]; then
    cat <<'EOF'
Usage: bash scripts/install-deps.sh [--no-rust]

Installs host packages with apt and the Rust toolchain with the official rustup
installer (https://rust-lang.org/tools/install/). Rust is installed under
/opt/rust and linked into /usr/local/bin. Run as the desktop user; sudo is used
only for these installs. Existing kernel, driver, and firmware are untouched.
EOF
    exit 0
fi
hmacos_require_host

apt_packages=(
    build-essential git curl ca-certificates pkg-config ninja-build
    python3 python3-venv python3-pip python3-dev
    libglib2.0-dev libpixman-1-dev libfdt-dev libffi-dev zlib1g-dev
    libgmp-dev nettle-dev libslirp-dev libvulkan-dev
    libx11-dev libx11-xcb-dev libxkbcommon-dev libwayland-dev
    gdb llvm-21 spirv-tools glslang-tools vulkan-tools x11-utils x11-xserver-utils
)
runtimes=(x11vnc)

printf 'Installing apt packages (sudo)...\n'
sudo apt-get update
sudo apt-get install -y --no-install-recommends "${apt_packages[@]}"
command -v x11vnc >/dev/null || sudo apt-get install -y --no-install-recommends "${runtimes[@]}"

printf 'Installing Python build tools (sudo)...\n'
sudo python3 -m pip install --break-system-packages meson ninja qemu.qmp pycotap setuptools wheel

if [[ ${1:-} != --no-rust ]] && ! command -v cargo >/dev/null; then
    printf 'Installing Rust via the official rustup installer (sudo)...\n'
    curl --proto '=https' --tlsv1.2 -fsSL https://sh.rustup.rs -o /tmp/hmacos-rustup.sh
    sudo env RUSTUP_HOME=/opt/rust/rustup CARGO_HOME=/opt/rust/cargo \
        sh /tmp/hmacos-rustup.sh -y --profile minimal --no-modify-path
    rm -f /tmp/hmacos-rustup.sh
    sudo ln -sf /opt/rust/cargo/bin/rustc /opt/rust/cargo/bin/cargo /opt/rust/cargo/bin/rustup /usr/local/bin/
fi

printf '\nInstalled. Versions:\n'
for tool in gcc meson ninja rustc cargo gdb nvidia-smi; do
    printf '  %-10s %s\n' "$tool" "$(command -v "$tool" || echo missing)"
done
printf '\nNext: git submodule update --init --recursive && make build\n'
