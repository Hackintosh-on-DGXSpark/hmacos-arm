# run/ — operating the VM

These scripts only **run** a VM. Building lives in `../scripts/` and `make`.

| Script | Purpose |
| --- | --- |
| `vm-up.sh` | Start one disposable instance on the physical DGX desktop |
| `vm-stop.sh` | Stop the current instance (its whole process group) |
| `vm-status.sh` | Show the recorded instance, liveness, and recent logs |
| `screen-share.sh` | Optional: mirror the physical screen to a Mac (loopback VNC) |
| `doctor.sh` | Read-only host prerequisite report |

## Start

```sh
run/vm-up.sh 1800                        # clean guest image
run/vm-up.sh 1800 <instance>             # copy a stopped instance (keeps guest tools)
run/vm-up.sh 1800 "" --ssh-port 12222    # forward a loopback port to guest SSH
run/vm-up.sh 1800 "" --no-net            # no network device
```

`vm-up.sh` verifies `guest-image/`, copies the disk and AUX into a new
`vm-instance/<name>/`, starts the QEMU firmware handoff, and opens the Reims window on
the physical screen. The default network is QEMU user-mode networking (no host
bridge); SSH is reachable only through `--ssh-port` on loopback.

Keep the `vm-up.sh` terminal open; Ctrl-C stops that instance. Each run prints
its instance directory; pass that name as `source-instance` next time to keep
guest changes.

## Stop and inspect

```sh
run/vm-stop.sh
run/vm-status.sh
```

Per-instance evidence (`command.json`, `serial.log`, `qemu.log`,
`result.json`) is in `vm-instance/<name>/`.

## Remote viewing from a Mac (optional)

```sh
run/screen-share.sh 1800
# on the Mac:
#   ssh -N -o ExitOnForwardFailure=yes -L 127.0.0.1:15900:127.0.0.1:5900 <dgx-host>
#   open vnc://127.0.0.1:15900
```
