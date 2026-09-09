# Physical desktop migration

## Observed host

The physical GNOME session is Xorg on seat0, owned by UID 1000 (`spark`). At
inspection, loginctl session 3 was active/local/X11, the graphical session
manager supplied `DISPLAY=:1` and `/run/user/1000/gdm/Xauthority`, and RandR
reported `USB-C-2` active at 3840x2160. Display `:0` was not usable. No display
number or authorization path is now hard-coded in the launchers.

## Changes

- `dgx_desktop.py` resolves and validates the physical session without creating
  a display or copying its authentication cookie.
- `start_ventura_desktop.sh` and graphical `boot_ventura.py` use that resolver.
  The real desktop runtime directory is retained; VM caches/logs stay private.
- `share_dgx_desktop.sh` provides optional, bounded, authenticated screen
  mirroring on loopback port 5900. It starts neither a virtual desktop nor a
  persistent service. Mac access uses SSH forwarding and Screen Sharing.
- Current instructions are in `docs/physical-desktop.md`. Old Xvfb/TigerVNC
  experiment commands remain labeled as historical evidence, not instructions.
- Scripts unrelated to display selection (provisioning, guest installation,
  KVM/Vulkan/Metal probes) were audited and did not need display changes.

## Verification

| Check | Result |
| --- | --- |
| `python3 -B -m unittest discover -s experiments -p test_dgx_desktop.py -v` | Four tests passed, including multiple rejection cases |
| Launcher/sharing shell syntax, help, invalid limits, Mac refusal | Passed |
| Resolver over ordinary SSH | Returned the physical session's three environment values |
| Resolver with `sudo -n -u spark -g kvm timeout 20s python3 -B /home/spark/hmacos-arm/src/dgx_desktop.py` | Same physical session, exit 0 |
| `timeout --kill-after=5s 45s python3 -B /home/spark/hmacos-arm/src/check_desktop_share.py` | VNC authentication required and passed; 3840x2160 framebuffer; 1024 raw pixels received and discarded |
| Physical VM launch with saved tools run | Guarded GDB handoff passed; Reims selected NVIDIA GB10; window was viewable on the physical Xorg display |
| VM time bound | Exit 124 after 302.69 seconds for a 300-second request |

VM command:

```sh
bash /home/spark/hmacos-arm/src/start_ventura_desktop.sh 300 desktop-20260908-155305-178690
```

The resulting run is
`/home/spark/hmacos-arm/artifacts/linux-boots/desktop-20260908-193104-18430/`.
All five baseline checksums passed before its disposable copies were created.
The window was observed through `xwininfo`; a later screenshot attempt occurred
after the bounded VM had exited and did not produce a valid screenshot. No new
claim about rendering correctness or stability is made.

The VNC integration check uses an ephemeral private password, authenticates over
RFB, compares the server dimensions to physical RandR dimensions, and reads a
32x32 sample without retaining pixel contents. Its initial strict pixel-count
assumption failed because x11vnc appended an 18x18 software-cursor rectangle.
The test now verifies the requested rectangle and accepts additional in-bounds
raw rectangles. No screen-sharing product fix was required for that result.

The successful check's logs are in
`/home/spark/hmacos-arm/artifacts/desktop-share-check-timcyi02/`; its temporary
password file was removed after the server stopped. No default user sharing
password was installed. The macOS Screen Sharing application's interactive UI
was not driven by this test; its RFB transport/authentication path was checked.

Local private evidence is under `artifacts/linux-boot-logs/physical-desktop/`.
Deployment checked the prior remote launcher hashes and replaced those scripts
atomically. The resolver and helper scripts were deployed beside them in `src/`.

## Final host state

At 19:50 +08:00 the original physical Xorg PID 4351 and GNOME Shell PID 4494
were still running. No QEMU, x11vnc, Xvfb, or Xtigervnc test process remained,
and ports 5900, 5901, 5904, and 19001 had no listeners. NVIDIA remained on driver
580.159.03 and was idle. No kernel, driver, display mode, group membership,
firewall, host security setting, or persistent remote-access service was changed.
