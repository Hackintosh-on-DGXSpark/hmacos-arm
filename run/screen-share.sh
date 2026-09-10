#!/usr/bin/env bash
# Optionally mirror the physical DGX desktop for remote viewing from a Mac.
# Starts no X server and no persistent service; loopback only.
set -euo pipefail
source "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/../scripts/common.sh"

if [[ ${1:-} == -h || ${1:-} == --help ]]; then
    printf 'Usage: run/screen-share.sh [seconds] [password-file]\n'
    printf 'Mirror the physical X11 desktop on 127.0.0.1:5900; 60..1800 seconds, default 1800.\n'
    printf 'First use prompts for a separate VNC password; use SSH forwarding from the Mac.\n'
    exit 0
fi
seconds=${1:-1800}
password_file=${2:-$HMACOS_INSTANCE_DIR/.desktop-share/vnc.passwd}
if [[ $# -gt 2 || ! $seconds =~ ^[1-9][0-9]{0,3}$ ]] || (( seconds < 60 || seconds > 1800 )); then
    printf 'Specify a timeout between 60 and 1800 seconds.\n' >&2
    exit 2
fi
hmacos_require_host
umask 077

desktop_env=$(python3 -m hmacos_arm.desktop)
while IFS='=' read -r key value; do
    case "$key" in
        DISPLAY|XAUTHORITY|XDG_RUNTIME_DIR) export "$key=$value" ;;
        *) printf 'Unexpected desktop environment field.\n' >&2; exit 1 ;;
    esac
done <<< "$desktop_env"

x11vnc=$(hmacos_tool x11vnc)
test -x "$x11vnc"
if [[ -L $password_file ]]; then
    printf 'Use a private regular VNC password file, not a symlink.\n' >&2
    exit 1
fi
if [[ ! -e $password_file ]]; then
    if [[ ! -t 0 ]]; then
        printf 'Run this once interactively to create the VNC password file.\n' >&2
        exit 1
    fi
    mkdir -p -m 700 "$HMACOS_INSTANCE_DIR/.desktop-share"
    "$x11vnc" -storepasswd "$password_file"
    chmod 600 "$password_file"
fi
if [[ ! -f $password_file || ! -r $password_file || $(stat -c %u "$password_file") != $(id -u) ]] ||
    (( (8#$(stat -c %a "$password_file") & 077) != 0 )); then
    printf 'The VNC password file must belong to the desktop user and be readable only by its owner.\n' >&2
    exit 1
fi
python3 -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1",5900)); s.close()'
printf 'Sharing the same physical desktop %s, including keyboard/mouse control.\n' "$DISPLAY"
printf 'Listener: 127.0.0.1:5900. Time limit: %s seconds. Ctrl-C stops sharing only.\n' "$seconds"
exec timeout --foreground --kill-after=5s "${seconds}s" "$x11vnc" \
    -display "$DISPLAY" -auth "$XAUTHORITY" -rfbauth "$password_file" \
    -listen 127.0.0.1 -noipv6 -rfbport 5900 -forever -shared \
    -noxdamage -nowf -noscr -noclipboard -nosetclipboard
