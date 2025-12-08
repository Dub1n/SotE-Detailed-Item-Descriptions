PYTHON ?= .venv/bin/python

STAGE0 := scripts/build_aow/build_aow_stage0.py
STAGE1 := scripts/build_aow/build_aow_stage1.py
STAGE2 := scripts/build_aow/build_aow_stage2.py

KNOWN_TARGETS := stage0 stage1 stage2 stages all
EXTRA_ARGS := $(filter-out $(KNOWN_TARGETS),$(MAKECMDGOALS))

.PHONY: $(KNOWN_TARGETS)

stage0:
	$(PYTHON) $(STAGE0) $(if $(filter $@,$(MAKECMDGOALS)),$(EXTRA_ARGS))

stage1:
	$(PYTHON) $(STAGE1) $(if $(filter $@,$(MAKECMDGOALS)),$(EXTRA_ARGS))

stage2:
	$(PYTHON) $(STAGE2) $(if $(filter $@,$(MAKECMDGOALS)),$(EXTRA_ARGS))

stages: stage0 stage1 stage2

all: stages

# Swallow extra goals used as CLI args (e.g., --output /tmp/AoW-data-1.csv)
$(filter-out $(KNOWN_TARGETS),$(MAKECMDGOALS)):
	@:
