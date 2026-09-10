#!/usr/bin/env bash
# Report the current VM run and its recent evidence.
set -euo pipefail
source "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/../scripts/common.sh"

if [[ ${1:-} == -h || ${1:-} == --help ]]; then
    printf 'Usage: run/vm-status.sh\nShow the recorded run, whether it is alive, and recent logs.\n'
    exit 0
fi

run_file=$HMACOS_STATE_DIR/current-run
pid_file=$HMACOS_STATE_DIR/current.pid
if [[ ! -s $run_file ]]; then
    printf 'No VM recorded. Start one with run/vm-up.sh.\n'
    exit 0
fi
run=$(cat "$run_file")
dir=$HMACOS_RUNS_DIR/$run
printf 'run: %s\n' "$run"
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
