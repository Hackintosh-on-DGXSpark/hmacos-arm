#!/usr/bin/env bash
# Read-only runtime prerequisite report for the physical desktop.
set -euo pipefail
source "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/../scripts/common.sh"
exec python3 -m hmacos_arm.doctor "$@"
