# Guest vulkaninfo installation

## Verified result

Installed user-local macOS arm64 Vulkan tools in Ventura 13.6 (22G120) on the
Spark. The guest installer verified runtime checksums, then ran the summary
and full reports with independent 60-second bounds. Recovered `install.log`
records `summary_exit=0` and `full_exit=0`.

```text
Vulkan Instance Version: 1.3.280
apiVersion = 1.2.280
deviceName = Apple Paravirtual device
deviceType = PHYSICAL_DEVICE_TYPE_INTEGRATED_GPU
driverID = DRIVER_ID_MOLTENVK
driverName = MoltenVK
driverInfo = 1.2.8
```

The device vendor/device IDs are both zero in this virtual Metal device.
They do not identify GB10. Reims independently logged its only physical host
device as NVIDIA GB10, driver 580.159.03. No mock ICD was built or installed.

This verifies installation and Vulkan capability enumeration, not arbitrary
Vulkan rendering or compute correctness. The user observed black frames and
flicker while interacting with the desktop. Those rendering problems remain;
successful `vulkaninfo` does not resolve or invalidate that observation.

## Installation and sources

- Guest runtime: `~/.local/share/hmacos-vulkan/1.3.280/`.
- Guest command: `~/.local/bin/vulkaninfo`; the wrapper selects only the bundled
  MoltenVK ICD and loader. No shell startup file or system library was changed.
- Vulkan-Headers and Vulkan-Loader: `v1.3.280`.
- Vulkan-Tools: `vulkan-sdk-1.3.280.0`, built with cube, mock ICD, and tests off.
- Volk: `01986ac85fa2e5c70df09aeae9c907e27c5d50b2`, from Tools' known-good list.
- MoltenVK: official `v1.2.8` macOS release; its arm64 slice has minimum OS 11.0.
- Loader and vulkaninfo were built on the local Mac with Apple clang 21 and
  CMake 3.29.6, `CMAKE_OSX_ARCHITECTURES=arm64` and
  `CMAKE_OSX_DEPLOYMENT_TARGET=13.0`. Mach-O minimum versions and signatures
  were verified. No Vulkan GPU workload was executed on the local Mac.
- Downloads, build logs, and source trees are under
  `sysroot/downloads/guest-vulkan/`; binaries/build dependencies stay ignored.
- Installer sources: `experiments/install_guest_vulkan.sh`,
  `experiments/guest_vulkaninfo.sh`, `experiments/guest_moltenvk_icd.json`.
- Runtime archive SHA-256:
  `3d6db64e5bcc610d554d06d3c8f2b70a183409f1f2b3780ef74309c30396f828`.
- A FAT USB image delivered the offline package. No guest network, Xcode,
  Homebrew, SIP/AMFI relaxation, or host driver change was required.

## Evidence and saved guest

The installed guest disk is in this stopped Spark run:

```text
/home/spark/hmacos-arm/artifacts/linux-boots/desktop-20260908-155305-178690/
```

Screenshots and Reims/handoff/result logs are under local
`artifacts/linux-boot-logs/vulkaninfo-01/`. Recovered installer reports
(`install.log`, `summary.txt`, `summary.stderr`, `full.txt`, `full.stderr`)
are in `artifacts/guest-vulkan/results.img`, inspected read-only and detached.
An additional interactive recheck was attempted but was not recovered; only
the two installer-recorded runs above are claimed. The VM subsequently stopped
with recorded process exit -9 after 899.73 seconds. A clean guest shutdown was
not established. No QEMU process or source QMP socket remained at handoff.

The reusable original installer image is retained at
`/home/spark/hmacos-arm/artifacts/guest-vulkan/installer.img`, read-only. Its
working copy, not that template, received the guest reports.

## Self-service use

Current launches use the physical desktop, not the former TigerVNC session.
See [physical desktop access](../physical-desktop.md) for optional same-screen
viewing from the Mac. In a DGX terminal:

```sh
bash scripts/start_ventura_desktop.sh 1800 desktop-20260908-155305-178690
```

The second argument selects the stopped guest containing the installed tools.
The launcher copies its disk/AUX into a new private run, verifies the original
baseline, performs the existing GDB handoff automatically, and opens Reims on
the automatically resolved physical X11 display. It refuses a source with a remaining QMP socket. Without a source
argument, it copies the clean baseline, which does not contain these tools.
Use the newly printed run name next time if retaining subsequent guest changes.

In the macOS guest Terminal:

```sh
~/.local/bin/vulkaninfo --summary
~/.local/bin/vulkaninfo > ~/Desktop/vulkaninfo.txt 2>&1
```

Optional, for the current guest terminal only:

```sh
export PATH="$HOME/.local/bin:$PATH"
vulkaninfo --summary
```

Each VM has a maximum 1800-second runtime. Keep its Linux launcher terminal open;
Ctrl-C terminates that disposable VM. The user owns subsequent testing; no new
VM was started after they requested control. Source selection passed syntax and
CLI/path-validation checks but was not live-booted by the assistant afterward.

The original timeout command created a new process group outside desktop
cleanup. A bounded Linux reproduction demonstrated the mismatch. Adding
`--foreground` to the inner QEMU timeout fixed that reproduction; the actual
installation run also showed launcher Python, timeout, and QEMU in one group.
This is process-scoped cleanup, not a host-wide process kill.
