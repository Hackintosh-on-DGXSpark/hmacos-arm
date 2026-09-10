#!/bin/sh
# Run inside the disposable guest from the writable probe volume.
set -u
out="$(dirname "$0")"
exec > "$out/guest-results.log" 2>&1
date -u
id
sw_vers
sysctl hw.model
system_profiler -timeout 15 SPDisplaysDataType
ioreg -r -c IOGPU -l -w 0
"$out/metal-probe" --explicit-device --negative-control
printf 'negative_exit=%s\n' "$?"
"$out/metal-probe" --explicit-device
printf 'positive_exit=%s\n' "$?"
date -u
sync
