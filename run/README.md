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
run/vm-up.sh 300 "" --cpus 8             # bounded 8-vCPU boot experiment
```

`vm-up.sh` verifies `guest-image/`, copies the disk and AUX into a new
`vm-instance/<name>/`, starts the QEMU firmware handoff, and opens the Reims window on
the physical screen. The default network is QEMU user-mode networking (no host
bridge); SSH is reachable only through `--ssh-port` on loopback.

Keep the `vm-up.sh` terminal open; Ctrl-C stops that instance. Each run prints
its instance directory; pass that name as `source-instance` next time to keep
guest changes.

`--cpus` selects 1..8 vCPUs (default 1). The pinned QEMU includes the cross-vCPU
handoff locking and VMApple CPU-initialization handling needed for SMP. This
initializes the secondary CPUs' PAC context; per-task PAC key switching and
broader graphics compatibility remain incomplete. More vCPUs alone do not
establish better interactive performance.

Reims also needs `llvm-dis` and `spirv-val` **at runtime** to translate guest
Metal shaders. The launcher restores the project-local sysroot tool/library
paths and checks both tools before starting QEMU. `run/doctor.sh` reports their
resolved paths and versions; `METAL2VULKAN_LLVM_DIS` and
`METAL2VULKAN_SPIRV_VAL` can select explicit executables.
Set `HMACOS_SYSROOT` to reuse an existing private toolchain from a fresh checkout.

## Stop and inspect

```sh
run/vm-stop.sh
run/vm-status.sh
```

Per-instance evidence (`command.json`, `runtime-tools.json`, `serial.log`, `qemu.log`,
`result.json`) is in `vm-instance/<name>/`.

For black-screen diagnostics, inspect `tmp/reims-vgpu-fail.log` in that same
instance. Reims shader-translation errors and `present_content`/`present_black`
records are written there, not just to `qemu.log`. A host window or a successful
`launchd` boot alone does not confirm a working guest desktop.

## Remote viewing from a Mac (optional)

```sh
run/screen-share.sh 1800
# on the Mac:
#   ssh -N -o ExitOnForwardFailure=yes -L 127.0.0.1:15900:127.0.0.1:5900 <dgx-host>
#   open vnc://127.0.0.1:15900
```
