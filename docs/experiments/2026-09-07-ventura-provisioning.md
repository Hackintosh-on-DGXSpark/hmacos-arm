# Ventura Disk Provisioning

## Result

Provisioned **macOS Ventura 13.6, build 22G120** on the local Apple M5 Pro
(`Mac17,9`, macOS 26.4 / 25E246, 48 GiB RAM).

- Native Virtualization.framework restore completed with `Installer done: OK`.
- The installer reported guest shutdown and exited `0` at 13:04:38 +08:00.
- A separate normal boot reached language selection within 30 seconds.
- The 120-second VM-only capture showed Setup Assistant's Location Services
  page. Setup progressed during the GUI session; that state was preserved.
- The validation VM was stopped through the VZ API and the launcher exited `0`.
  This validation stop is distinct from a guest-initiated clean shutdown.
- Read-only disk inspection confirmed `SystemVersion.plist` reports `13.6`
  and `22G120`. The inspection mounts were detached afterward.
- The ECID encoded in `vm.json` matched AUX storage; derived AUX trimming was
  checked byte-for-byte. No VM identity is included in this report.

This establishes a provisioned Mac-hosted VM, **not** Linux boot or guest GPU
acceleration on the Spark. Completed user setup and guest SSH are unverified.
No host security settings or guest SIP/AMFI settings were changed by this work.

## Private Artifacts

Working bundle: `artifacts/ventura-13.6/`.
Clean restore backup: `artifacts/ventura-13.6-restore/`.
Read-only export snapshot: `artifacts/ventura-13.6-export/`.
All are excluded by `.gitignore` and stored below mode-0700 directories.

| File | Meaning | Size |
| --- | --- | --- |
| `disk.img` | Installed sparse system disk | 64 GiB logical, about 15 GiB allocated |
| `aux.img` | Original VZ AUX/NVRAM | 33,570,816 bytes |
| `aux.img.trimmed` | AUX without its 16 KiB outer header | 33,554,432 bytes |
| `vm.json` | Matched hardware model, identity, and configuration | 559 bytes |
| `AVPBooter.vmapple2.bin` | Bootloader copied from this Mac | 304,352 bytes |
| `SHA256SUMS` | Checksums of the five files above | Private manifest |

The export snapshot passed `shasum -a 256 -c SHA256SUMS` for all five files.
Its configuration has two vCPUs, 4 GiB RAM, NAT networking, and relative disk
paths. Guest-only PNG captures and installer/boot logs are under
`artifacts/ventura-capture/` and `artifacts/provisioning-logs/`.

## Provenance And Commands

Official Apple restore image, 12,893,555,341 bytes:

<https://updates.cdn-apple.com/2023FallFCS/fullrestores/042-55833/C0830847-A2F8-458F-B680-967991820931/UniversalMac_13.6_22G120_Restore.ipsw>

SHA-256 matched Apple's HTTPS response metadata:
`9bf095739b8b2d5ebd20f7e8de938f10bc449f9843de21c4a41ae54d73526728`.
The download completed with aria2 1.37.0, exit `0`. Direct Apple CDN access was
faster than the configured proxy; TLS verification remained enabled.

Provisioner: signed `s-u/macosvm` release `0.2-3` in `sysroot/macosvm/`.
Run from the new VM directory, with a 1200-second process limit:

```sh
macosvm --disk disk.img,size=64g --aux aux.img \
  --restore /absolute/path/UniversalMac_13.6_22G120_Restore.ipsw \
  --net nat --mac 52:54:00:76:61:70 -c 2 -r 4g --no-serial vm.json
```

For boot evidence, built tag `0.2-3`, commit
`c21fd7414bab38b0a2474b351b90378bdef98325`, with
`experiments/macosvm-capture.patch`, using `make -j2`. The patch captures only
the application's VZ view through AppKit, not the host desktop, every 30 seconds
and stops the VM after four captures. Both binaries passed `codesign --verify`.

```sh
HMACOS_CAPTURE_DIR=/absolute/path/to/private/captures \
  macosvm --gui --no-serial vm.json
dd if=aux.img of=aux.img.trimmed bs=16384 skip=1
```

## Spark Transfer

Destination: `/home/spark/hmacos-arm/artifacts/ventura-13.6-22G120/`.

**Transfer completed at 15:22 +08:00 on 2026-09-07.** All eight resumed parts
and reconstruction/verification exited `0`. `STAGING_COMPLETE` exists, and a
fresh `sha256sum -c SHA256SUMS` on the Spark passed for all five files before
the next experiment. The destination is a verified, read-only base bundle.

The SSH route was bandwidth-limited. A direct sparse rsync was interrupted and
the disk was compressed with `zstd -T2 -9 --long=27` to 11.3 GiB, then divided
into eight parts. The initial eight-stream transfer hit its 40-minute bounds,
leaving about 4.9 GiB of resumable data. A subsequent `rsync --append` test sent
only the missing 131,848,647 bytes of `part-ah`, exited `0`, and the complete
part's SHA-256 matched on both hosts.

`experiments/stage_ventura.py` finished those parts with two workers.
Each upload is bounded to 1800 seconds; reconstruction/verification to 900
seconds. It reconstructs a separate sparse `disk.img.upload`, checks the disk
hash before replacing the earlier partial disk, verifies all five manifest
entries, makes the base files read-only, then creates `STAGING_COMPLETE`.
Failure leaves an `INCOMPLETE` status instead of declaring the bundle ready.

Progress: `artifacts/provisioning-logs/stage-background.log`.
Final status: `artifacts/provisioning-logs/stage-status.txt`.
Do not boot or modify the Spark destination before its completion marker exists.
