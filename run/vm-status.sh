#!/usr/bin/env bash
# Report the current VM instance and its recent evidence.
set -euo pipefail
source "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/../scripts/common.sh"

if [[ ${1:-} == -h || ${1:-} == --help ]]; then
    printf 'Usage: run/vm-status.sh\nShow the recorded instance, whether it is alive, and recent logs.\n'
    exit 0
fi

name_file=$HMACOS_INSTANCE_DIR/.current-instance
pid_file=$HMACOS_INSTANCE_DIR/.current.pid
if [[ ! -s $name_file ]]; then
    printf 'No VM recorded. Start one with run/vm-up.sh.\n'
    exit 0
fi
name=$(cat "$name_file")
dir=$HMACOS_INSTANCE_DIR/$name
printf 'instance: %s\n' "$name"
if [[ -s $pid_file ]] && kill -0 -- "-$(cat "$pid_file")" 2>/dev/null; then
    printf 'state: running (group %s)\n' "$(cat "$pid_file")"
else
    printf 'state: not running\n'
fi
ps -C qemu-system-aarch64 -o pid,etime,pcpu,pmem,comm 2>/dev/null || true
[[ -f $dir/result.json ]] && { printf 'result:\n'; cat "$dir/result.json"; }
for log in handoff.log qemu.log serial.log; do
    if [[ -s $dir/$log ]]; then
        printf '\n== %s (last 5 lines) ==\n' "$log"
        tail -n 5 "$dir/$log"
    fi
done
