#!/usr/bin/env bash
# User-local build tools only. Native development packages are listed in docs/build.md.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"
if [[ ${1:-} == --help ]]; then
    printf 'Usage: bash scripts/setup_build_tools.sh\nInstall pinned build tools into the project sysroot only.\n'
    exit 0
fi
[[ $# -eq 0 ]] || { printf 'No arguments expected.\n' >&2; exit 2; }
if [[ $(uname -s)/$(uname -m) != Linux/aarch64 || $(id -u) -eq 0 ]]; then
    printf 'Run as a non-root user on the Arm Linux DGX.\n' >&2
    exit 2
fi
mkdir -p "$HMACOS_SYSROOT/downloads"
if [[ ! -x $HMACOS_SYSROOT/build-venv/bin/python ]]; then
    python3 -m venv "$HMACOS_SYSROOT/build-venv"
fi
"$HMACOS_SYSROOT/build-venv/bin/python" -m pip install -r "$HMACOS_ROOT/deps/build-requirements.txt"
rust=$(python3 -c 'import json,os; print(json.load(open(os.environ["HMACOS_ROOT"]+"/deps/sources.lock.json"))["toolchain"]["rust"])')
if ! command -v rustc >/dev/null || [[ $(rustc --version) != "rustc $rust "* ]]; then
    url=https://static.rust-lang.org/rustup/archive/1.28.2/aarch64-unknown-linux-gnu/rustup-init
    curl --proto '=https' --tlsv1.2 -fL --connect-timeout 15 --max-time 600 "$url" -o "$HMACOS_SYSROOT/downloads/rustup-init"
    curl --proto '=https' --tlsv1.2 -fL --connect-timeout 15 --max-time 60 "$url.sha256" -o "$HMACOS_SYSROOT/downloads/rustup-init.sha256"
    (cd "$HMACOS_SYSROOT/downloads" && sha256sum -c rustup-init.sha256)
    chmod 700 "$HMACOS_SYSROOT/downloads/rustup-init"
    timeout --kill-after=10s 1800s "$HMACOS_SYSROOT/downloads/rustup-init" -y \
        --profile minimal --default-toolchain "$rust" --no-modify-path
fi
rustc --version
meson --version
