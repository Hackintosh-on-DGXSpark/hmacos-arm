PYTHON ?= python3
export PYTHONPATH := $(CURDIR)/src
export PYTHONDONTWRITEBYTECODE := 1

.PHONY: help test lint format check setup fetch build probes
help:
	@echo 'Development and build targets (running a VM lives in run/, not make):'
	@echo '  make check    unit tests, lint, and formatting (no VM inputs)'
	@echo '  make setup    project-local Rust/Meson tools (see docs/build.md)'
	@echo '  make fetch    hash-verified sources and patches'
	@echo '  make build    native arm64 QEMU/Reims Vulkan build'
	@echo '  make probes   build host KVM/Vulkan probes'
	@echo
	@echo 'Run the VM:  run/vm-up.sh  |  Stop: run/vm-stop.sh  |  See: run/README.md'

test:
	$(PYTHON) -m unittest discover -s tests -v

lint:
	ruff check src/hmacos_arm tests tools scripts
	ruff format --check src/hmacos_arm tests tools scripts
	clang-format --dry-run --Werror probes/kvm/probe.c probes/vulkan/compute.c probes/metal/metal_probe.m
	@for file in run/*.sh scripts/*.sh tools/guest-vulkan/*.sh probes/metal/*.sh; do bash -n "$$file" || exit; done

format:
	ruff check --fix src/hmacos_arm tests tools scripts
	ruff format src/hmacos_arm tests tools scripts
	clang-format -i probes/kvm/probe.c probes/vulkan/compute.c probes/metal/metal_probe.m

check: test lint
setup:
	bash scripts/setup_build_tools.sh
fetch:
	bash scripts/fetch_dependencies.sh
build:
	bash scripts/build_host.sh
probes:
	bash scripts/build_probes.sh
