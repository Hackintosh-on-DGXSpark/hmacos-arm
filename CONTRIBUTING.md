# Contributing

Keep changes small and preserve the source/guest boundary. Original tooling is
MIT licensed; modifications to dependencies retain upstream licenses and notices.

1. Install `requirements-dev.txt` in a local virtual environment.
2. Run `make check`; use `make format` for original Python/C/Objective-C code.
3. Keep dependency changes in `deps/` and `patches/`, with exact revisions and
   archive hashes. Do not reformat downloaded third-party source trees.
4. Test Linux/KVM/NVIDIA changes on the DGX, with explicit bounds and a physical
   desktop. Unit tests do not establish GPU correctness.
5. Record exact commands, versions, exit states, and limitations in a dated
   experiment note. Do not include credentials, VM identities, or Apple bytes.

Do not replace driver/kernel packages, change persistent security policy, stop
unrelated workloads, or alter another developer's changes as part of a test.
No subagent or formal review workflow is required to use or contribute to the
project. Keep host screen sharing optional and separate from native VM graphics.
