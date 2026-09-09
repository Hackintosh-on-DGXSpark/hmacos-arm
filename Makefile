PYTHON ?= python3
export PYTHONPATH := $(CURDIR)/src
export PYTHONDONTWRITEBYTECODE := 1

.PHONY: help test lint format check doctor setup fetch build run share probes
help:
	@echo 'make check         unit tests, lint, and formatting checks (no VM inputs)'
	@echo 'make doctor        read-only DGX runtime checks'
	@echo 'make setup         project-local Rust/Meson tools (see docs/build.md first)'
	@echo 'make fetch         hash-verified sources and patches'
	@echo 'make build         native arm64 QEMU/Reims Vulkan build'
	@echo 'make run           VM on the physical desktop; SOURCE_RUN=... preserves a prior run'
	@echo 'make share         optional physical-screen mirror for SSH access from a Mac'
	@echo 'make probes        build host KVM/Vulkan probes on the DGX'

test:
	$(PYTHON) -m unittest discover -s tests -v

lint:
	ruff check src/hmacos_arm tests tools scripts
	ruff format --check src/hmacos_arm tests tools scripts
	clang-format --dry-run --Werror probes/kvm/probe.c probes/vulkan/compute.c probes/metal/metal_probe.m
	@for file in scripts/*.sh tools/guest-vulkan/*.sh probes/metal/*.sh; do bash -n "$$file" || exit; done

format:
	ruff check --fix src/hmacos_arm tests tools scripts
	ruff format src/hmacos_arm tests tools scripts
	clang-format -i probes/kvm/probe.c probes/vulkan/compute.c probes/metal/metal_probe.m

check: test lint
doctor:
	bash scripts/doctor.sh
setup:
	bash scripts/setup_build_tools.sh
fetch:
	bash scripts/fetch_dependencies.sh
build:
	bash scripts/build_host.sh
run:
	bash scripts/start_ventura_desktop.sh $${SECONDS_LIMIT:-1800} "$(SOURCE_RUN)"
share:
	bash scripts/share_dgx_desktop.sh $${SECONDS_LIMIT:-1800}
probes:
	bash scripts/build_probes.sh
