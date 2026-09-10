# run/ — operating the VM

These scripts are what you use day to day. They only **run** the VM; building
the emulator lives in `../scripts/` and `make`.

| Script | Purpose |
| --- | --- |
| `vm-up.sh` | Start one disposable Ventura VM on the physical DGX desktop |
| `vm-stop.sh` | Stop the current VM (its whole process group); disks remain |
| `vm-status.sh` | Show the recorded run, liveness, and recent logs |
| `screen-share.sh` | Optional: mirror the physical screen to a Mac (loopback VNC) |
| `doctor.sh` | Read-only host prerequisite report |

## Start

```sh
run/vm-up.sh 1800                         # clean baseline
run/vm-up.sh 1800 desktop-20260908-155305-178690   # keep installed guest tools
run/vm-up.sh 1800 "" --ssh-port 12222     # add a loopback SSH forward
```

`vm-up.sh` verifies the baseline, copies the disk and AUX into a new directory
under `$HMACOS_RUNS_DIR`, starts the guarded handoff, and opens the Reims window
on the physical screen. No VNC, Xvfb, or `DISPLAY` fiddling is needed.

Keep the `vm-up.sh` terminal open; Ctrl-C stops that VM. Every launch prints its
run directory. To retain guest changes, pass that directory's name as
`source-run` next time.

## Stop and inspect

```sh
run/vm-stop.sh
run/vm-status.sh
```

Each run's artifacts (command, serial, QEMU log, handoff, `result.json`) are in
`$HMACOS_STATE_DIR/runs/<name>/`.

## Remote viewing from a Mac (optional)

```sh
run/screen-share.sh 1800
# then, on the Mac:
#   ssh -N -o ExitOnForwardFailure=yes -L 127.0.0.1:15900:127.0.0.1:5900 <dgx-host>
#   open vnc://127.0.0.1:15900
```

See `../docs/physical-desktop.md` for details and limitations.
