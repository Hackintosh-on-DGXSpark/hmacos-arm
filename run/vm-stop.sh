#!/usr/bin/env bash
# Stop the VM started by run/vm-up.sh (its whole process group).
set -euo pipefail
source "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/../scripts/common.sh"

if [[ ${1:-} == -h || ${1:-} == --help ]]; then
    printf 'Usage: run/vm-stop.sh\nStop the current VM and clear the run pointer. Disks are retained.\n'
    exit 0
fi
hmacos_require_host

pid_file=$HMACOS_STATE_DIR/current.pid
run_file=$HMACOS_STATE_DIR/current-run
if [[ ! -s $pid_file || ! -s $run_file ]]; then
    printf 'No VM is recorded as running.\n'
    exit 0
fi
pid=$(cat "$pid_file")
run=$(cat "$run_file")
if [[ ! $pid =~ ^[0-9]+$ ]] || ! kill -0 -- "-$pid" 2>/dev/null; then
    printf 'Recorded VM "%s" is not running; clearing pointer.\n' "$run"
    rm -f "$pid_file" "$run_file"
    exit 0
fi
printf 'Stopping VM "%s" (group %s)...\n' "$run" "$pid"
kill -TERM -- "-$pid" 2>/dev/null || true
for ((i = 0; i < 100; i++)); do
    kill -0 -- "-$pid" 2>/dev/null || break
    sleep 0.1
done
if kill -0 -- "-$pid" 2>/dev/null; then
    printf 'VM did not stop on SIGTERM; sending SIGKILL.\n'
    kill -KILL -- "-$pid" 2>/dev/null || true
fi
rm -f "$pid_file" "$run_file"
printf 'Stopped. Disks remain in %s/%s\n' "$HMACOS_RUNS_DIR" "$run"
