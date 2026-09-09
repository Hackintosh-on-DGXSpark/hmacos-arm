#!/usr/bin/env bash
# Hardware-backed Ventura window on the logged-in physical DGX desktop.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"

if [[ $# -eq 1 && $1 == --help ]]; then
    printf 'Usage: bash start_ventura_desktop.sh [seconds] [source-run]\n'
    printf 'NVIDIA graphics on the active physical X11 desktop; 60..1800 seconds, default 1800.\n'
    printf 'Copies the clean baseline, or a stopped source-run to retain installed tools.\n'
    printf 'Ctrl-C stops this VM. Source disks are never booted in place.\n'
    exit 0
fi
seconds=${1:-1800}
source_run=${2:-}
if [[ $# -gt 2 || ! $seconds =~ ^[1-9][0-9]{0,3}$ ]] || (( seconds < 60 || seconds > 1800 )); then
    printf 'Specify a timeout between 60 and 1800 seconds.\n' >&2
    exit 2
fi
if [[ -n $source_run && ! $source_run =~ ^[a-zA-Z0-9-]+$ ]]; then
    printf 'Invalid source-run name.\n' >&2
    exit 2
fi
if [[ $(uname -s)/$(uname -m) != Linux/aarch64 || $(id -u) -eq 0 ]]; then
    printf 'Run this as the desktop user on the Arm Linux DGX, not the local Mac or root.\n' >&2
    exit 2
fi
if [[ ! -c /dev/kvm ]]; then
    printf '/dev/kvm is unavailable; enable a supported host KVM configuration first.\n' >&2
    exit 1
fi
if [[ ! -r /dev/kvm || ! -w /dev/kvm ]]; then
    if [[ $(id -gn) == kvm ]]; then
        printf 'KVM access is still unavailable in the kvm group; refusing repeated sudo attempts.\n' >&2
        exit 1
    fi
    exec sudo -n -u "$(id -un)" -g kvm timeout --kill-after=10s "$((seconds + 750))s" \
        env HMACOS_ROOT="$HMACOS_ROOT" HMACOS_STATE_DIR="$HMACOS_STATE_DIR" HMACOS_SYSROOT="$HMACOS_SYSROOT" HMACOS_BUNDLE="$HMACOS_BUNDLE" HMACOS_QEMU="$HMACOS_QEMU" \
        bash "$(readlink -f "$0")" "$seconds" "$source_run"
fi

umask 077
root=$HMACOS_ROOT
base=$HMACOS_BUNDLE
desktop_env=$(python3 -m hmacos_arm.desktop)
while IFS='=' read -r key value; do
    case "$key" in
        DISPLAY|XAUTHORITY|XDG_RUNTIME_DIR) export "$key=$value" ;;
        *) printf 'Unexpected desktop environment field.\n' >&2; exit 1 ;;
    esac
done <<< "$desktop_env"
printf 'Using physical desktop DISPLAY=%s\n' "$DISPLAY"
mkdir -p -m 700 "$HMACOS_STATE_DIR/linux-boots"
exec 9>"$HMACOS_STATE_DIR/desktop-launch.lock"
if ! flock -n 9; then
    printf 'Another desktop launcher is running; stop it before starting another.\n' >&2
    exit 1
fi
test -f "$base/STAGING_COMPLETE"
source=$base
if [[ -n $source_run ]]; then
    source=$HMACOS_STATE_DIR/linux-boots/$source_run
    if [[ ! -d $source || -L $source || -e $source/qmp.sock ]]; then
        printf 'Source must be a stopped run with its QMP socket removed: %s\n' "$source" >&2
        exit 1
    fi
    for file in disk.img aux.img.trimmed; do
        [[ -f $source/$file && ! -L $source/$file ]]
    done
fi
test -r "$XAUTHORITY"
timeout 10s xdpyinfo -display "$DISPLAY" >/dev/null
python3 -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1",19001)); s.close()'
nvidia-smi --query-gpu=name,driver_version,utilization.gpu --format=csv,noheader
printf 'Verifying the immutable Ventura baseline...\n'
timeout 300s python3 -m hmacos_arm.bundle "$base"

name=desktop-$(date +%Y%m%d-%H%M%S)-$$
run=$HMACOS_STATE_DIR/linux-boots/$name
mkdir -m 700 "$run"
printf 'Preparing disposable storage: %s\n' "$run"
timeout 300s cp --reflink=auto --sparse=always "$source/disk.img" "$source/aux.img.trimmed" "$run/"
chmod 600 "$run/disk.img" "$run/aux.img.trimmed"

# A separate process group keeps cleanup confined to this launcher and its VM.
setsid env QEMU_VMAPPLE_PAC_DEFAULTS=1 python3 -m hmacos_arm.boot "$name" \
    --accelerator kvm --seconds "$seconds" --gdb-port 19001 --hardware-graphics \
    >"$run/launcher.log" 2>&1 &
vm=$!
cleanup() {
    trap - EXIT INT TERM HUP
    if kill -0 -- "-$vm" 2>/dev/null; then
        kill -TERM -- "-$vm" 2>/dev/null || true
        for ((i=0; i<50; i++)); do
            kill -0 -- "-$vm" 2>/dev/null || break
            sleep 0.1
        done
        kill -KILL -- "-$vm" 2>/dev/null || true
    fi
    wait "$vm" 2>/dev/null || true
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
trap 'exit 129' HUP

for ((i=0; i<300; i++)); do
    [[ -S $run/qmp.sock ]] && break
    kill -0 "$vm" 2>/dev/null || break
    sleep 0.1
done
if [[ ! -S $run/qmp.sock ]]; then
    printf 'VM did not start; inspect %s/launcher.log and qemu.log\n' "$run" >&2
    exit 1
fi
env HMACOS_RUN_DIR="$run" HMACOS_TIMEBASE_HZ=1000000000 HMACOS_GDB_PORT=19001 \
    HMACOS_BOOT_ARGS='-v serial=11 debug=0x14c' \
    timeout --kill-after=5s 90s "$(hmacos_tool gdb)" -nx -q -batch \
    -x "$root/scripts/inject_ventura_kvm.gdb" >"$run/handoff.log" 2>&1
printf 'Boot handoff complete. Look for Reims vGPU on the physical DGX desktop.\n'
printf 'VM time limit: %s seconds. Logs: %s\n' "$seconds" "$run"
printf 'Keep this terminal open. Ctrl-C stops the disposable VM; disks are retained for inspection.\n'
wait "$vm"
python3 -c 'import json,sys; r=json.load(open(sys.argv[1])); print(r); sys.exit(0 if r["exit"] in (0,124) else 1)' "$run/result.json"
