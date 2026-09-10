# Security and publication boundaries

This is not a production isolation product. Use disposable guests and modest
resource limits. The research PAC-defaults shim does not emulate architectural
key switching; the in-QEMU firmware handoff is specific to tested Ventura
inputs. Do not use sensitive production workloads or credentials in the guest.

- Never commit or redistribute Apple firmware, IPSWs, disk/AUX images, VM
  identities, captured Apple shaders, private keys, passwords, or session exports.
- `artifacts/`, `sysroot/`, downloads, logs, and local environment files are
  ignored. Review the staged file list before every commit; ignore rules alone
  are not a security audit.
- Baselines must be verified and never booted in place. Launchers use copies and
  refuse active source runs. Keep matched disk, AUX, firmware, and identity data
  together. Checksums do not establish software ownership or licensing rights.
- Use the existing NVIDIA driver and kernel. No GPU unbinding, VFIO, permission
  changes to `/dev/kvm`, persistent group changes, or disabled host security are
  required by the default workflow.
- QMP and optional VNC are restricted to loopback or private Unix sockets.
  The default VM has no network device. Do not expose debug ports to a network.
- Optional VNC mirrors the whole physical desktop and permits input. Use a
  separate private password and an SSH tunnel; it is not screen/session isolation.
- Never use `xhost +`, unauthenticated VNC, or SSH host-key verification bypasses.
- CI must never receive Apple input bundles or guest credentials.

Report security issues privately to the repository maintainer through an
authenticated hosting-service channel. Do not attach private VM artifacts to a
public issue. No vulnerability-response SLA is offered for this research project.
