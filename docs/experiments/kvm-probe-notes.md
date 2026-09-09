# Standalone Arm64 KVM Probe

## Test Contract

Bounded Linux arm64 KVM diagnostic on `dsec-dgx-spark`, not a macOS boot test.
No installs, persistent access changes, kernel/driver changes, VM disks,
firmware, or external endpoints are needed.

One vCPU starts at EL1h with DAIF masked and the stage-1 MMU disabled. One
2 MiB RAM slot begins at GPA `0x40000000`. The independent guest payload
computes `((0x1234 * 0x56) + 0x78) XOR 0x4b564d5000000000`, then stores the
64-bit result `0x4b564d5000061df0` to unmapped GPA `0x10000000`. Assertions
check `KVM_EXIT_MMIO`, address, length, write direction, payload, and guest
X0/X1/X2/X4 through `KVM_GET_ONE_REG`. `TEST_EXPECTED_VALUE` changes only the
host-side oracle, never the guest instruction sequence.

If both PAuth capabilities are available, both vCPU feature bits are enabled.
The guest additionally signs and authenticates pointer `0x40000100` with
PACIA/AUTIA, modifier `0x5678`, and a public synthetic APIA key. The check
requires a changed signed pointer with the original low 48 bits, and exact
pointer recovery. These are not HINT-space instructions. There is no claim
about corrupted-PAC rejection, Apple PAC algorithms, or macOS compatibility.

The probe has an 8-second `SIGALRM` watchdog and at most eight EINTR retries
per ioctl (nine attempts total). The runner adds `timeout 10s`. Unexpected
ioctl errors, unexpected exits, and assertion failures are nonzero; no optional
ioctl failures are silently ignored. Normal completion closes/unmaps resources;
early exit or signal termination also releases this unforked process's resources.

## Results: 2026-09-07

See [the main experiment report](2026-09-07-dgx-spark.md) for host versions,
commands, exit statuses, and the remote log location.

- Base probe: pass, including arithmetic/MMIO and PACIA/AUTIA roundtrip.
- Wrong expected-value build: exit `1` at the MMIO value assertion as intended.
- `PROBE_16K`: actual execution with the stage-1 MMU enabled and 16 KiB page
  tables, using 32 MiB identity-mapped blocks. The registered RAM remains 2 MiB.
- `PROBE_VMAPPLE_HVC`: forwards `0xc1000000` to userspace, validates its argument,
  returns a synthetic `0x42`, and resumes the guest successfully.
- Combined 16 KiB/HVC build: pass, including the PAuth roundtrip.
- Guest PSCI can be reduced from `1.3` to `1.1`; timer frequency is 1 GHz.
- Apple-specific `APCTL_EL12` is absent from the KVM register interface (`ENOENT`).

## Interpretation Boundaries

Guest ID values come from `KVM_GET_ONE_REG` after vCPU feature initialization,
not direct host register reads. They describe the KVM-exposed CPU, which can
be filtered. PAuth fields are logged as raw nibbles, not generic Booleans:
ISAR1 APA `[7:4]`, API `[11:8]`, GPA `[27:24]`, GPI `[31:28]`; ISAR2 APA3
`[15:12]`, GPA3 `[11:8]`. Different fields identify different authentication
algorithm families and their encoded feature levels.

`ID_AA64MMFR0_EL1.TGran16[23:20]` uses `0` for **not supported**, `1` for
supported, and `2` for support including 52-bit input/output addresses with
FEAT_LPA2. This is not the same encoding as TGran4/TGran64, whose unsupported
encoding is `0xf`. Host `PAGE_SIZE=4096` is separate from guest stage-1 granule
capabilities. The default build leaves the MMU off; `PROBE_16K` exercises the
16 KiB translation-table granule but uses block descriptors, not L3 page mappings.
PARange is an encoded field, not a bit count; the default `KVM_CREATE_VM(0)`
40-bit IPA limit is also separate from guest-reported PARange.

PSCI and timer outputs are capability/register observations, not interrupt,
timer-expiry, SMP, or PSCI hypercall tests. Apple-range forwarding is a synthetic
transport test, not an implementation of Apple's PAC services.
`KVM_CAP_ARM_USER_IRQ` reports the
version of device-output-level notification support with a userspace irqchip;
`KVM_CAP_COUNTER_OFFSET` reports the counter-offset API. No VGIC is created.
The pending MMIO store is inspected but not completed by reentering `KVM_RUN`;
the diagnostic VM is destroyed instead. This is not a migration/resume test.

Source references, distinct from local execution evidence:

- [Linux KVM API](https://docs.kernel.org/virt/kvm/api.html): vCPU initialization,
  paired PAuth enablement, `KVM_RUN`, one-reg interface, and capability semantics.
- [Arm ID_AA64MMFR0_EL1 register reference (2024 mirror)](https://www.df.lth.se/~getz/ARM/SysReg/AArch64-id_aa64mmfr0_el1.html):
  raw TGran16 and PARange encodings. Unknown/reserved TGran16 values are not
  interpreted as supported by the probe.
