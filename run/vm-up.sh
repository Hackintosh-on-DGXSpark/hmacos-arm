#!/usr/bin/env bash
# Start one disposable Ventura VM on the logged-in physical DGX desktop.
set -euo pipefail
source "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/../scripts/common.sh"

usage() {
    cat <<'EOF'
Usage: run/vm-up.sh [seconds] [source-instance] [--ssh-port PORT] [--no-net]

  seconds           VM lifetime, 60..1800 (default 1800).
  source-instance   A stopped instance name under vm-instance/ to copy
                    (keeps installed guest tools). Omit for the clean image.
  --ssh-port PORT   Forward that loopback port to guest SSH.
  --no-net          Start with no network device (default is user-mode network).

Graphics use the physical X11 session and NVIDIA Vulkan. The guest image and the
source instance are never booted in place; a new vm-instance/<name>/ is created.
EOF
}

seconds=1800
source_name=""
ssh_port=""
net=()
positionals=()
while [[ $# -gt 0 ]]; do
    case "$1" in
        -h|--help) usage; exit 0 ;;
        --ssh-port) shift; ssh_port=${1:-} ;;
        --no-net) net=(--no-net) ;;
        *) positionals+=("$1") ;;
    esac
    shift
done
if [[ ${#positionals[@]} -ge 1 ]]; then seconds=${positionals[0]}; fi
if [[ ${#positionals[@]} -ge 2 ]]; then source_name=${positionals[1]}; fi
if [[ ${#positionals[@]} -gt 2 || ! $seconds =~ ^[1-9][0-9]{0,3}$ ]] || (( seconds < 60 || seconds > 1800 )); then
    printf 'Specify a timeout between 60 and 1800 seconds.\n' >&2
    exit 2
fi
if [[ -n $source_name && ! $source_name =~ ^[a-zA-Z0-9-]+$ ]]; then
    printf 'Invalid source-instance name.\n' >&2
    exit 2
fi
if [[ -n $ssh_port ]] && { [[ ! $ssh_port =~ ^[1-9][0-9]{0,4}$ ]] || ((ssh_port > 65535)); }; then
    printf 'Invalid --ssh-port.\n' >&2
    exit 2
fi
hmacos_require_host

HMACOS_REEXEC_ARGV=(bash "$(readlink -f "${BASH_SOURCE[0]}")" "$seconds" "$source_name" "${net[@]}")
[[ -n $ssh_port ]] && HMACOS_REEXEC_ARGV+=(--ssh-port "$ssh_port")
hmacos_require_kvm

umask 077
base=$HMACOS_BUNDLE
mkdir -p -m 700 "$HMACOS_INSTANCE_DIR"
exec 9>"$HMACOS_INSTANCE_DIR/.vm.lock"
flock -n 9 || { printf 'Another VM launch is in progress.\n' >&2; exit 1; }

source=$base
if [[ -n $source_name ]]; then
    source=$HMACOS_INSTANCE_DIR/$source_name
    if [[ ! -d $source || -L $source || -e $source/qmp.sock ]]; then
        printf 'Source must be a stopped instance with its QMP socket removed: %s\n' "$source" >&2
        exit 1
    fi
    for file in disk.img aux.img.trimmed; do
        [[ -f $source/$file && ! -L $source/$file ]]
    done
fi
printf 'Verifying the immutable guest image...\n'
timeout 300s python3 -m hmacos_arm.bundle "$base"

name=vm-$(date +%Y%m%d-%H%M%S)-$$
instance=$HMACOS_INSTANCE_DIR/$name
mkdir -m 700 "$instance"
printf 'Preparing disposable storage: %s\n' "$instance"
timeout 300s cp --reflink=auto --sparse=always "$source/disk.img" "$source/aux.img.trimmed" "$instance/"
chmod 600 "$instance/disk.img" "$instance/aux.img.trimmed"

supervisor=(python3 -m hmacos_arm.supervisor "$name" --accelerator kvm --seconds "$seconds" \
    --renderer nvidia --serial-socket "${net[@]}")
[[ -n $ssh_port ]] && supervisor+=(--ssh-port "$ssh_port")

setsid env QEMU_VMAPPLE_PAC_DEFAULTS=1 "${supervisor[@]}" >"$instance/launcher.log" 2>&1 &
vm=$!
printf '%s\n' "$name" >"$HMACOS_INSTANCE_DIR/.current-instance"
printf '%s\n' "$vm" >"$HMACOS_INSTANCE_DIR/.current.pid"

cleanup() {
    trap - EXIT INT TERM HUP
    if kill -0 -- "-$vm" 2>/dev/null; then
        kill -TERM -- "-$vm" 2>/dev/null || true
        for ((i = 0; i < 50; i++)); do
            kill -0 -- "-$vm" 2>/dev/null || break
            sleep 0.1
        done
        kill -KILL -- "-$vm" 2>/dev/null || true
    fi
    wait "$vm" 2>/dev/null || true
    if [[ $(cat "$HMACOS_INSTANCE_DIR/.current.pid" 2>/dev/null) == "$vm" ]]; then
        rm -f "$HMACOS_INSTANCE_DIR/.current-instance" "$HMACOS_INSTANCE_DIR/.current.pid"
    fi
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
trap 'exit 129' HUP

printf 'Instance "%s" starting on the physical desktop. Ctrl-C stops it.\n' "$name"
printf 'Instance: %s\n' "$instance"
wait "$vm"
python3 -c 'import json,sys; r=json.load(open(sys.argv[1])); print(r); sys.exit(0 if r["exit"] in (0,124) else 1)' "$instance/result.json"
