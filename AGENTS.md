# Project Context

Research running an arm64 macOS virtual machine on Arm Linux with actual
hardware-accelerated guest graphics. A booted desktop, CPU-rendered Vulkan, or a
working host compositor alone does not establish guest GPU acceleration.

## Development Machine

- The user-provided NVIDIA DGX Spark development machine is accessible with
  `ssh dsec-dgx-spark`.
- Run Linux, KVM, and NVIDIA GPU experiments on this remote machine, not on the
  local macOS workstation.
- The user has authorized provisioning a Ventura VM on the local Apple Silicon
  Mac. Use it only to prepare/validate matching disk, AUX/NVRAM, firmware, and
  identity inputs; Linux/KVM testing still belongs on the Spark.
- Local `artifacts/` contains private provisioning inputs and VM bundles and
  must remain untracked. Local downloaded tools belong in ignored `sysroot/`.
- Use `ssh -o BatchMode=yes -o ConnectTimeout=15 dsec-dgx-spark` for automated
  connections. Do not bypass SSH host-key verification.
- Inspect the host before installing dependencies or launching experiments.
  Keep builds, downloads, and runtime outputs in a project-specific directory.
- The confirmed remote working directory is `/home/spark/hmacos-arm`, owned by
  the SSH user `spark`. This is an operator-specific deployment, not a path to
  hard-code in runtime code. Keep downloaded tools in `sysroot/`, not system paths.
- The user prefers direct experiments and concise result logs. Do not write
  detailed implementation plans or run formal code-review workflows for them.
- The SSH user is not a member of `kvm`. For bounded KVM tests, use
  `sudo -n -u spark -g kvm timeout ...` for process-scoped access; do not change
  group membership or `/dev/kvm` permissions.

## Physical Desktop

- The Spark now has a physical screen. Do not start Xvfb, Xtigervnc, or a
  separate desktop for VM graphics. Resolve the active local X11 session with
  `src/hmacos_arm/desktop.py`; do not assume `:0` or reuse old Xauthority paths.
- On 2026-09-08 the physical GNOME/Xorg session used display `:1`, GDM's
  `/run/user/1000/gdm/Xauthority`, and a 3840x2160 monitor on `USB-C-2`.
  These are observations, not fixed configuration. Wayland is not supported by
  the current launcher/sharing helpers and must not trigger a virtual fallback.
- `start_ventura_desktop.sh [seconds] [source-run]` opens the VM on that physical
  desktop. Source run `desktop-20260908-155305-178690` contains guest vulkaninfo;
  copying the clean baseline does not preserve installed tools.
- Optional `share_dgx_desktop.sh` mirrors the same physical screen with a
  private VNC password, only on `127.0.0.1:5900`. Use SSH forwarding to Mac port
  15900. It creates no virtual display or persistent service. See
  `docs/physical-desktop.md` for commands and limitations.

## Ventura Inputs

- Ventura 13.6 (`22G120`) was restored and boot-verified on the local Mac.
  The working VM is `artifacts/ventura-13.6/`; launch from that directory so
  the relative storage paths in `vm.json` resolve correctly.
- `artifacts/ventura-13.6-restore/` preserves the clean post-install state.
  `artifacts/ventura-13.6-export/` is the read-only snapshot paired with the
  compressed transfer parts. Do not modify either baseline.
- The Spark destination is
  `/home/spark/hmacos-arm/artifacts/ventura-13.6-22G120/`. Staging completed on
  2026-09-07 at 15:22 +08:00; all five checksums were reverified afterward.
  Require `STAGING_COMPLETE` and passing `sha256sum -c SHA256SUMS` before use.
- The original compressed-transfer logs are in `artifacts/provisioning-logs/`.
  The one-off uploader has been retired. New bundles follow `docs/inputs.md`
  and `python3 -m hmacos_arm.bundle --mark` after legitimate input preparation.
- Software-rendered desktop login and interaction were verified on the Spark
  on 2026-09-08. Guest SSH access remains unverified. No SIP/AMFI changes were
  made by provisioning; never record the supplied guest password in files.

## Verified Graphics State

- The Reims pipeline reached a working Lavapipe desktop (`sw-06`), confirmed
  interactively by the user.
- NVIDIA GB10 Vulkan passed a guest Metal compute/readback test in `hw-02`:
  two runs of 65,536 exact uint32 results, plus a one-error negative control.
  See `docs/experiments/2026-09-08-gb10-metal.md` for commands and evidence.
- Use `python3 -m hmacos_arm.boot --hardware-graphics` for NVIDIA, not an external ICD
  override combined with `--software-graphics` (which explicitly forces CPU).
- `MTLCreateSystemDefaultDevice()` is still nil in the tested guest. The probe
  needs `--explicit-device` to select the sole enumerated Apple paravirtual GPU.
  Rendering artifacts and texture staging declines remain unresolved; do not
  describe this as complete Metal compatibility or production-ready graphics.

## Experiment Rules

- Runtime Python lives under `src/hmacos_arm/`; native entry points are in
  `scripts/`, original probes in `probes/`, and dependency pins/patches in
  `deps/` and `patches/`. Do not copy dependencies into tracked source.
- Run `make check` with `requirements-dev.txt` installed before committing.
  Source/build verification belongs on the DGX; CI runs only synthetic checks.
- Before publishing, inspect staged content and run
  `python3 scripts/audit_publication.py`. Never stage `session-*.md`, raw logs,
  VM identities, Apple bytes, or credentials. Retain upstream patch licenses.

- Begin with read-only checks, then bounded CPU/KVM and hardware Vulkan tests.
- Keep the existing kernel, firmware, NVIDIA driver, and running workloads
  intact. Ask before changes requiring a reboot, driver replacement, GPU
  unbinding/passthrough, or persistent host security changes.
- Use timeouts and modest CPU/RAM allocations. Clean up only processes and
  artifacts created by the current experiment.
- Bind experimental VM monitor, debug, and display endpoints to loopback or
  private Unix sockets; use SSH forwarding for access.
- Record exact versions, commands, exit status, observed results, and limitations
  in `docs/experiments/`. Separate source-reported results from local evidence.
- Never commit or redistribute Apple firmware, IPSWs, VM disks, VM identities,
  credentials, or private keys. Use legitimately obtained local inputs.
- Do not claim macOS GPU acceleration until a guest Metal workload produces
  correct results through a verified physical host GPU, not Lavapipe/LLVMpipe.
- GPU translation via Reims and Vulkan is distinct from PCI/VFIO passthrough;
  do not assume macOS has an NVIDIA GB10 driver.
