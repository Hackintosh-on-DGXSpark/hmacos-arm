#!/usr/bin/env bash
# Stop the VM started by run/vm-up.sh (its whole process group).
set -euo pipefail
source "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/../scripts/common.sh"

if [[ ${1:-} == -h || ${1:-} == --help ]]; then
    printf 'Usage: run/vm-stop.sh\nStop the current instance and clear the pointer. Storage is retained.\n'
    exit 0
fi
hmacos_require_host

pid_file=$HMACOS_INSTANCE_DIR/.current.pid
name_file=$HMACOS_INSTANCE_DIR/.current-instance
if [[ ! -s $pid_file || ! -s $name_file ]]; then
    printf 'No VM is recorded as running.\n'
    exit 0
fi
pid=$(cat "$pid_file")
name=$(cat "$name_file")
if [[ ! $pid =~ ^[0-9]+$ ]] || ! kill -0 -- "-$pid" 2>/dev/null; then
    printf 'Recorded instance "%s" is not running; clearing pointer.\n' "$name"
    rm -f "$pid_file" "$name_file"
    exit 0
fi
printf 'Stopping instance "%s" (group %s)...\n' "$name" "$pid"
kill -TERM -- "-$pid" 2>/dev/null || true
for ((i = 0; i < 100; i++)); do
    kill -0 -- "-$pid" 2>/dev/null || break
    sleep 0.1
done
kill -KILL -- "-$pid" 2>/dev/null || true
rm -f "$pid_file" "$name_file"
printf 'Stopped. Storage remains in %s/%s\n' "$HMACOS_INSTANCE_DIR" "$name"
