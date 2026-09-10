#!/bin/sh
# Offline, user-local installation and bounded verification inside Ventura.
set -eu
case "$(uname -s):$(uname -m):$(sysctl -n hw.model 2>/dev/null || true)" in
    Darwin:arm64:VirtualMac*) ;;
    *) printf 'Run this inside the arm64 VirtualMac guest, not the host.\n' >&2; exit 2 ;;
esac
umask 077
payload="$(dirname "$0")"
exec > "$payload/install.log" 2>&1
date -u
sw_vers
root="$HOME/.local/share/hmacos-vulkan"
dest="$root/1.3.280"
mkdir -p "$root" "$HOME/.local/bin"
if ! test -e "$dest"; then
    tar -xzf "$payload/vulkan-runtime.tar.gz" -C "$root"
fi
(cd "$dest" && shasum -a 256 -c SHA256SUMS)
if test -e "$HOME/.local/bin/vulkaninfo" || test -L "$HOME/.local/bin/vulkaninfo"; then
    cmp "$payload/vulkaninfo" "$HOME/.local/bin/vulkaninfo"
else
    install -m 700 "$payload/vulkaninfo" "$HOME/.local/bin/vulkaninfo"
fi
summary=0
/usr/bin/perl -e 'alarm 60; exec @ARGV' "$HOME/.local/bin/vulkaninfo" --summary \
    > "$dest/summary.txt" 2> "$dest/summary.stderr" || summary=$?
full=0
/usr/bin/perl -e 'alarm 60; exec @ARGV' "$HOME/.local/bin/vulkaninfo" \
    > "$dest/full.txt" 2> "$dest/full.stderr" || full=$?
printf 'summary_exit=%s\nfull_exit=%s\n' "$summary" "$full"
cp "$dest/summary.txt" "$dest/summary.stderr" "$dest/full.txt" "$dest/full.stderr" "$payload/"
cat "$dest/summary.txt" "$dest/summary.stderr"
sync
if test "$summary" -ne 0 || test "$full" -ne 0 || \
    ! grep -Fq 'Apple Paravirtual device' "$dest/summary.txt" || \
    ! grep -Fq 'MoltenVK' "$dest/summary.txt"; then
    printf 'FAIL: expected MoltenVK device enumeration was not verified.\n'
    exit 1
fi
printf 'PASS: guest vulkaninfo summary and full report enumerate the Apple paravirtual device via MoltenVK.\n'
printf 'Installed command: %s/.local/bin/vulkaninfo --summary\n' "$HOME"
