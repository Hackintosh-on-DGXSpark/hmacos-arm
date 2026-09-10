#!/bin/sh
set -eu
root="$HOME/.local/share/hmacos-vulkan/1.3.280"
export DYLD_LIBRARY_PATH="$root/lib"
export VK_DRIVER_FILES="$root/share/vulkan/icd.d/MoltenVK_icd.json"
unset VK_ICD_FILENAMES
exec "$root/libexec/vulkaninfo" "$@"
