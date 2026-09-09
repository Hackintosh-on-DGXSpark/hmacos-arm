# Private guest inputs

The project does not distribute macOS or restore it on the DGX. Prepare a
matching Ventura 13.6 (`22G120`) VM using legitimate Apple software and Apple
virtualization tooling, or bring an already prepared matching bundle. Comply
with the applicable software licenses. A local Mac is used only for this
optional preparation step, not as part of normal DGX runtime operation.

The private bundle contains:

| File | Required meaning |
| --- | --- |
| `disk.img` | Restored raw guest disk |
| `aux.img` | Matching original AUX/NVRAM |
| `aux.img.trimmed` | The same AUX with its 16 KiB outer header removed, as tested for Ventura |
| `vm.json` | macosvm configuration containing the matching encoded machine identity |
| `AVPBooter.vmapple2.bin` | Matching, legitimately obtained Apple boot firmware |
| `SHA256SUMS` | SHA-256 manifest naming exactly the five files above |
| `STAGING_COMPLETE` | Created only after all five hashes pass |

Do not mix firmware, AUX, identity, and disks from different VMs or versions.
The kernel handoff is intentionally guarded for the tested Ventura layout.
Neither a matching filename nor a checksum proves cross-version compatibility.

Prepare the manifest while the source VM is stopped. For a prepared source
bundle, the manifest command is:

```sh
shasum -a 256 disk.img aux.img aux.img.trimmed vm.json AVPBooter.vmapple2.bin > SHA256SUMS
```

Transfer the files into the DGX checkout's private
`artifacts/ventura-13.6-22G120/`, preserving sparse disk allocation where
possible. Alternatively point `HMACOS_BUNDLE` at a private existing bundle.
Do not overwrite an existing baseline. In the DGX checkout, verify and mark it:

```sh
PYTHONPATH=src python3 -m hmacos_arm.bundle --mark
```

With a non-default location:

```sh
PYTHONPATH=src python3 -m hmacos_arm.bundle /absolute/path/to/bundle --mark
export HMACOS_BUNDLE=/absolute/path/to/bundle
```

The verifier rejects unexpected manifest paths, duplicates, missing files,
symlinks, and hash mismatches. It never creates a completion marker after a
failed check. Keep baseline files read-only; the runtime refuses to boot their
inodes and uses new disposable copies instead.

`docs/experiments/2026-09-07-ventura-provisioning.md` records the original
provisioning commands and limitations. Historical transfer/account-setup
reports are retained; their one-off helper scripts were retired and are not
runtime dependencies.
