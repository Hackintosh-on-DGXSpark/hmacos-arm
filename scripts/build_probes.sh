#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"
if [[ ${1:-} == -h || ${1:-} == --help ]]; then
    printf 'Usage: bash scripts/build_probes.sh\nBuild the KVM and Vulkan host probes. Does not run them.\n'
    exit 0
fi
[[ $(uname -s)/$(uname -m) == Linux/aarch64 ]] || { printf 'Build host probes on the Arm Linux DGX.\n' >&2; exit 2; }
out=$HMACOS_ROOT/build/probes
mkdir -p "$out"
cc -O2 -Wall -Wextra -Werror "$HMACOS_ROOT/probes/kvm/probe.c" -o "$out/kvm-probe"
cc -O2 -Wall -Wextra -Werror -DPROBE_16K -DPROBE_VMAPPLE_HVC \
    "$HMACOS_ROOT/probes/kvm/probe.c" -o "$out/kvm-vmapple-probe"
cc -O2 -Wall -Wextra -Werror -DTEST_EXPECTED_VALUE=0 \
    "$HMACOS_ROOT/probes/kvm/probe.c" -o "$out/kvm-negative"
glslangValidator -V --target-env vulkan1.2 "$HMACOS_ROOT/probes/vulkan/compute.comp" -o "$out/compute.spv"
spirv-val --target-env vulkan1.2 "$out/compute.spv"
include=()
if [[ -d $HMACOS_SYSROOT/usr/include ]]; then include=(-I"$HMACOS_SYSROOT/usr/include"); fi
cc -O2 -Wall -Wextra -Werror "${include[@]}" "$HMACOS_ROOT/probes/vulkan/compute.c" \
    -Wl,-l:libvulkan.so.1 -o "$out/vulkan-compute"
cc -O2 -Wall -Wextra -Werror -DPROBE_HOST_IMPORT "${include[@]}" \
    "$HMACOS_ROOT/probes/vulkan/compute.c" -Wl,-l:libvulkan.so.1 -o "$out/vulkan-host-import"
printf 'Built host probes in %s. No guest or GPU workload was launched.\n' "$out"
