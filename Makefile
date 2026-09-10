PYTHON ?= python3
export PYTHONPATH := $(CURDIR)/src
export PYTHONDONTWRITEBYTECODE := 1

.PHONY: help check test lint format deps submodules build probes
help:
	@echo 'Build and check (running a VM lives in run/, not make):'
	@echo '  make check       unit tests, lint, and formatting (no guest inputs)'
	@echo '  make deps        system-wide build dependencies (apt + rustup; sudo)'
	@echo '  make submodules  fetch the pinned component submodules'
	@echo '  make build       arm64 QEMU/Reims Vulkan build into build/'
	@echo '  make probes      host KVM/Vulkan probes into build/probes/'
	@echo
	@echo 'Run:  run/vm-up.sh  |  Stop: run/vm-stop.sh  |  See: run/README.md'

test:
	$(PYTHON) -m unittest discover -s tests -v

lint:
	ruff check src/hmacos_arm tests in-guest-tools scripts
	ruff format --check src/hmacos_arm tests in-guest-tools scripts
	clang-format --dry-run --Werror probes/kvm/probe.c probes/vulkan/compute.c in-guest-tools/metal-probe/metal_probe.m
	@for file in run/*.sh scripts/*.sh in-guest-tools/**/*.sh; do bash -n "$$file" || exit; done

format:
	ruff check --fix src/hmacos_arm tests in-guest-tools scripts
	ruff format src/hmacos_arm tests in-guest-tools scripts
	clang-format -i probes/kvm/probe.c probes/vulkan/compute.c in-guest-tools/metal-probe/metal_probe.m

check: test lint
deps:
	bash scripts/install-deps.sh
submodules:
	git submodule update --init --recursive
build:
	bash scripts/build_host.sh
probes:
	bash scripts/build_probes.sh
