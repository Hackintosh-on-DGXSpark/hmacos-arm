# Physical DGX desktop

This is the current workflow. Do not start Xvfb, Xtigervnc, or a second desktop
for the VM. Reims opens a normal window on the logged-in physical DGX desktop.

## Start the guest

Log in as your desktop user on the physical screen. In the checkout, run in a DGX terminal, or over ordinary
SSH without X forwarding:

```sh
bash scripts/start_ventura_desktop.sh 1800 desktop-20260908-155305-178690
```

The source run above contains the installed guest `vulkaninfo`. Omit the second
argument to start from the clean Ventura baseline instead. Every launch copies
the source disk/AUX into a new run; use the printed new run name next time to
retain subsequent changes. Never copy or reuse an active run as a source.

The launcher verifies the baseline, obtains process-scoped KVM access, and runs
the guarded GDB handoff automatically. It uses one vCPU, 8 GiB RAM, and NVIDIA
Vulkan. The runtime limit is 60..1800 seconds; Ctrl-C in the launcher terminal
stops that experiment, not the host desktop. This is a research VM, so save any
guest work before stopping it.

In the guest's Terminal:

```sh
~/.local/bin/vulkaninfo --summary
```

## View from the Mac

The optional viewer mirrors the same physical screen. It does not start a
virtual X server or a new login session. Remote keyboard/mouse input controls
the whole logged-in host desktop, not just the VM, and is shared with the person
at the physical keyboard.

In a second DGX terminal:

```sh
bash scripts/share_dgx_desktop.sh 1800
```

For remote setup from the Mac, allocate a terminal so the first password prompt
works. Replace `dgx-spark` with your SSH alias and adjust the checkout path if
it is not `~/hmacos-arm`:

```sh
ssh -t dgx-spark 'bash ~/hmacos-arm/scripts/share_dgx_desktop.sh 1800'
```

First use prompts for a separate VNC password. It is stored only in the private
`artifacts/desktop-share/vnc.passwd` file; do not reuse the guest or SSH password.
VNC authentication has only eight significant password characters. SSH supplies
the transport encryption. The sharing script refuses symlinked, foreign-owned,
or group/world-readable password files.

In another Mac terminal, keep this tunnel running:

```sh
ssh -N -o ExitOnForwardFailure=yes -L 127.0.0.1:15900:127.0.0.1:5900 dgx-spark
```

Open macOS Screen Sharing from a separate terminal:

```sh
open vnc://127.0.0.1:15900
```

Enter the VNC password selected above. There is no separate VNC username. Do
not open ports in the firewall or bind this server to a public address. The
server listens only on `127.0.0.1:5900`; the old 5901/5904 virtual-desktop ports
are not used. Sharing stops after its own timeout or Ctrl-C; stopping sharing
does not stop the VM or the physical desktop. Clipboard synchronization is off.

## Display selection

`src/hmacos_arm/desktop.py` resolves the active local X11 session on `seat0`, checks it is
owned by the invoking user, reads DISPLAY/XAUTHORITY from that user's graphical
session manager, and requires an active non-virtual RandR output. Both the
high-level launcher and low-level graphical boot use it. Stale DISPLAY values
from SSH or old virtual desktops are not trusted. No authorization cookie is
printed, copied, or modified, and no `xhost` exception is needed.

On 2026-09-08 the physical GNOME/Xorg desktop happened to be `:1`, using
`/run/user/1000/gdm/Xauthority`, with `USB-C-2` at 3840x2160. A display number of
`:1` does not itself mean a virtual display. These values are discovered, not
hard-coded. The actual desktop's XDG runtime directory is retained, while VM
temporary files and shader caches remain private to the run.

No active physical login, an unreadable authorization file, another user's
session, or only virtual/disconnected outputs cause a clear failure. This
workflow currently supports Xorg/X11, not Wayland. If the session changes to
Wayland, choose a compositor-supported desktop-sharing solution instead; these
scripts will not create a virtual-display fallback or change the login session.

## Known limits

Moving to the physical display does not fix the existing Reims rendering
artifacts, flicker, or default-Metal-device selection issue. Hardware-backed
Metal compute correctness and guest Vulkan enumeration were verified separately;
neither guarantees correct rendering in every application. No kernel, driver,
GPU binding, persistent remote-access service, or host security policy is changed
by these scripts.
