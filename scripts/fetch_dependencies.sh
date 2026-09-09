#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"
exec python3 -m hmacos_arm.sources "$@"
