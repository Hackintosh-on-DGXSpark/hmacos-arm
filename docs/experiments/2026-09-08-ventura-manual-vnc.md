# Ventura manual VNC handoff, 2026-09-08

Historical experiment: the isolated Xvfb/TigerVNC access below is no longer the
launch workflow. Use [the physical desktop workflow](../physical-desktop.md)
for current VM launches and optional same-screen access from macOS.

## Scope and host

- Continued the previous session on `dsec-dgx-spark`; Linux/KVM ran only there.
- Host: arm64, Linux `6.17.0-1026-nvidia`, NVIDIA GB10 driver `580.159.03`.
- Read-only initial check: GPU utilization 0%; existing TigerVNC `:1` on
  loopback port 5901. That desktop and its server were left intact.
- The staged Ventura baseline had `STAGING_COMPLETE`; running
  `env -C /home/spark/hmacos-arm/artifacts/ventura-13.6-22G120 timeout 300s sha256sum -c SHA256SUMS`
  exited 0 with all five files passing before use.

## Guest control attempt

- Existing `control-02` was `prelaunch`, not booted. The standard guarded GDB
  handoff with `HMACOS_BOOT_ARGS="-v -s serial=11 debug=0x14c"` exited 0.
- UART `sw_vers` returned macOS 13.6, build 22G120.
- `timeout --kill-after=5s 360s python3 /home/spark/hmacos-arm/src/install_guest_ssh.py control-02 --port 12222`
  exited 0. It installed a separate key-only diagnostic service on the
  disposable disk and pinned its host key from UART. It changed no existing
  user password and made no SIP/AMFI changes.
- After `sync` and guest `halt`, QMP reported `shutdown`; QMP `quit` released
  the disk before copying it into `sw-06`.
- Normal-boot SSH to loopback 12222 did not succeed: banner timeouts and resets.
  The user interrupted the retry and requested manual VNC instead. The reason
  for the guest SSH failure remains unverified; installation is not proof of
  a running or reachable service.

## Active graphical experiment

- Private evidence: `/home/spark/hmacos-arm/artifacts/linux-boots/sw-06/`.
- Boot used the existing Reims/QEMU build, one KVM vCPU, 8 GiB shared,
  16 KiB-aligned file-backed RAM, and explicitly selected Lavapipe.
- Launch:

```sh
sudo -n -u spark -g kvm env QEMU_VMAPPLE_PAC_DEFAULTS=1 DISPLAY=:97 XAUTHORITY=/home/spark/hmacos-arm/artifacts/linux-boots/sw-06/Xauthority timeout --kill-after=10s 1830s python3 /home/spark/hmacos-arm/src/boot_ventura.py sw-06 --accelerator kvm --seconds 1800 --gdb-port 19001 --software-graphics --serial-socket --ssh-port 12222
```

- Normal-boot GDB handoff exited 0, using `HMACOS_TIMEBASE_HZ=1000000000`,
  `HMACOS_GDB_PORT=19001`, and `HMACOS_BOOT_ARGS="-v serial=11 debug=0x14c"`.
- Capture `display-current.png` showed the existing user's login screen.
  Post-login desktop behavior and keyboard/mouse response were not yet tested.
- The VM started approximately 11:17:28 +08:00 with a 1800-second bound;
  expected stop is approximately 11:47:28 +08:00. It was left running for
  the user's manual interaction, not reported as cleaned up.

## Manual access

- Started a bounded x11vnc for `:97`, listening only on `127.0.0.1:5904`, with
  `-forever -shared -noxdamage -noclipboard -nosetclipboard -noipv6`.
  It uses the current TigerVNC session's existing password file via `-rfbauth`;
  no password value was copied into scripts or this report.
- Verification: `ss` showed both the untouched port 5901 and new port 5904.
  A live RFB handshake returned `RFB 003.008` with only security type 2
  (VNC authentication), not unauthenticated access.
- Remmina 1.4.35 is installed on the DGX. In the existing DGX VNC desktop:

```sh
remmina -c vnc://127.0.0.1:5904
```

- Alternatively, from the local Mac:

```sh
ssh -N -o ExitOnForwardFailure=yes -L 127.0.0.1:15904:127.0.0.1:5904 dsec-dgx-spark
open vnc://127.0.0.1:15904
```

Keep the SSH command running; execute `open` in a separate local terminal.

Use the existing DGX VNC password for the viewer, then the separately supplied
guest credential at the macOS login screen. No guest SSH is needed for this.
Closing a viewer does not stop the bounded VM. Do not start another QEMU
against the active raw disks or rerun this launcher in an existing run directory.

## Manual input follow-up

- The user launched Remmina at 11:23:20 +08:00. x11vnc recorded its connection
  at 11:23:46 and normal authenticated framebuffer exchange at 11:24:06.
  The reported console message was informational, not a connection error.
  X11 inspection confirmed a viewable Remmina window on desktop 0 of `:1`.
- On the user's keyboard-input report, QMP `info usb` showed a USB keyboard
  and tablet; guest serial logs also showed their HID drivers starting.
- `XGetInputFocus` on `:97` returned `0x1` (PointerRoot), not an explicitly
  focused Reims window. This is not by itself proof that every key was lost.
  This bare Xvfb session has no window manager to establish click-to-focus.
- A targeted runtime change used
  `XSetInputFocus(display, 0x200002, RevertToParent, CurrentTime)` on `:97`.
  Readback verified `focus_before=0x1`, `focus_after=0x200002` (Reims vGPU).
  The command exited 0; no VM restart, input injection, or code rebuild occurred.
- A bounded 20-second X11 event count then observed four key presses and eight
  releases at the Reims window. No key values or typed content were recorded.
- Source inspection confirmed winit keys map to evdev, the MMIO adapter calls
  `reims_vgpu_shim_input_key`, and QEMU sends/synchronizes the event to the
  virtual input device. There is no missing sync in that path.
- Subsequent private capture `display-key-events.png` showed the user's
  post-login Ventura desktop, Finder menu bar, Dock, and Keyboard Setup
  Assistant. The assistant did not type the login credential or submit login;
  the user was interacting through VNC. This verifies progress beyond the
  login screen after the focus change, not a controlled proof that focus was
  the sole cause of the earlier symptom.
- Keyboard layout identification and broader app typing/window-interaction
  tests remain for the user. Focus was fixed only for this running X session;
  future bare-Xvfb launches should explicitly establish input focus again.

## Interpretation

Manual checks should cover login, TextEdit typing, Finder menus, window movement,
and resizing. A displayed login screen alone does not verify desktop usability.
This experiment uses CPU-rendered Vulkan, not NVIDIA-backed guest graphics.
Neither a responsive desktop nor guest-reported Metal support establishes
physical GPU acceleration; a correct guest Metal workload on verified physical
host GPU execution remains required.
