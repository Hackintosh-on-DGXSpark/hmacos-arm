# Path refactor: run/ vs scripts/ vs runtime library

Date: 2026-09-10. Host: `dsec-dgx-spark` (arm64, GB10, driver 580.159.03).

## What changed

The project previously mixed two lifecycles and put the VM behind `make`:

- **Building the emulator** and **running a guest** were interleaved.
- `make run` / `make share` wrapped shell launchers, hiding the operation.
- `src/hmacos_arm/boot.py` (227 lines) mixed argv construction, process
  supervision, and QEMU-RAM inspection.
- Runs lived under `artifacts/linux-boots/`; there was no stop/status entry point.

Now:

| Path | Responsibility |
| --- | --- |
| `run/` | Operating the VM: `vm-up.sh`, `vm-stop.sh`, `vm-status.sh`, `screen-share.sh`, `doctor.sh` |
| `scripts/` | Building and engineering: `build_host.sh`, `fetch_dependencies.sh`, `setup_build_tools.sh`, `build_probes.sh`, `inject_ventura_kvm.gdb`, `audit_publication.py`, `common.sh` |
| `src/hmacos_arm/qemu.py` | QEMU argv + renderer environment (pure, unit-tested) |
| `src/hmacos_arm/supervisor.py` | Launch, wait for QMP, run the handoff, record `result.json` |
| `src/hmacos_arm/config.py` | Paths, `runs/`, and the current-run pointer; baseline/run safety |
| `docs/`, `deps/`, `patches/`, `probes/`, `tools/` | unchanged responsibilities |

`make` now only builds and checks. Running is `run/vm-up.sh`; stopping is
`run/vm-stop.sh`; inspecting is `run/vm-status.sh`. The launcher resolves the
physical desktop, verifies the baseline, copies storage into a new
`artifacts/runs/<name>/`, and records that name so stop/status can find it.

The retired `boot.py` also dropped the historical `--inspect-after` RAM-dump and
`--trace-aes` options; they were one-off diagnostics not used by the launchers.
They can be reintroduced as explicit probes if needed.

## Verification

- Local and remote `make check`: 28 synthetic tests plus Ruff/clang-format/shell
  syntax. New tests cover QEMU argv shape (renderer, shared RAM, network, GDB) and the
  run-pointer round trip.
- On the Spark, `run/vm-up.sh 240 desktop-20260908-155305-178690`:
  - all five baseline files verified;
  - run created at `artifacts/runs/vm-20260910-120326-77339`;
  - GDB handoff passed (`1 CPU timebase properties: 24000000 -> 1000000000 Hz`,
    GIC workaround verified);
  - Reims selected `NVIDIA GB10` and presented the first frame;
  - the `Reims vGPU` window was `Map State: IsViewable` on the physical desktop.
- `run/vm-status.sh` reported the run, liveness, and logs from the same data.

To make the source-run naming work on this host, the old `artifacts/linux-boots/`
was renamed to `artifacts/runs/` (same filesystem, metadata only). Historical
documents still reference `linux-boots/`; that is the pre-refactor name.

## Still to do: avoid the per-boot disk copy

The launcher still copies the whole allocated `disk.img` each boot. On this ext4
host `cp --reflink=auto` cannot clone, so the copy is real (measured 15-16 GiB;
one cold-cache boot took tens of seconds). A qcow2 overlay backed by the
read-only raw base would store each run as a small delta.

That is not adopted yet because it needs verification first:

1. `qemu-img` is not built (`configure` uses `--disable-tools`); building it is a
   small addition but must be pinned.
2. The vmapple machine opens the root disk twice — once as `if=pflash` (its BDIF
   backdoor) and once as `virtio-blk` — so a qcow2 overlay would be written by two
   QEMU block nodes unless the drives are restructured to one shared node. That
   needs a real boot test to rule out metadata corruption.

Both are tracked as the next disk-performance task; correctness comes before it.
