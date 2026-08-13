# ==============================================================================
# Rasa Community Resources — root orchestration
# ==============================================================================
# Single source of truth for the Rasa Pro pin: ./RASA_PRO_VERSION
# Per-project day-to-day targets still live in each resource's Makefile.
# ==============================================================================

GREEN   := $(shell tput -Txterm setaf 2 2>/dev/null)
YELLOW  := $(shell tput -Txterm setaf 3 2>/dev/null)
BLUE    := $(shell tput -Txterm setaf 4 2>/dev/null)
MAGENTA := $(shell tput -Txterm setaf 5 2>/dev/null)
RED     := $(shell tput -Txterm setaf 1 2>/dev/null)
RESET   := $(shell tput -Txterm sgr0 2>/dev/null)

PYTHON  ?= python3
UV      := $(shell command -v uv 2>/dev/null)
ROOT    := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
SCRIPTS := $(ROOT)/scripts

# Optional override: make migrate VERSION=3.19.0.dev5
VERSION ?=
# KEEP_GOING=1 continues after a project failure (check-all / test-all / lock-all / …)
KEEP_GOING ?= 0

VERSION_ARGS := $(if $(VERSION),--version $(VERSION),)
LIST         := $(PYTHON) $(SCRIPTS)/list_projects.py
MIGRATE      := $(PYTHON) $(SCRIPTS)/migrate_rasa_pro.py
CHECK        := $(PYTHON) $(SCRIPTS)/check_project.py

PROJECTS := $(shell $(LIST) --paths-only 2>/dev/null)

.DEFAULT_GOAL := help

.PHONY: help check-uv list status migrate lock-all install-all \
        check-all test-all verify-all clean-all \
        _require-projects

help: ## Show this help message
	@echo ''
	@echo '$(MAGENTA)Rasa Community Resources$(RESET)'
	@echo '  Pin file: $(GREEN)RASA_PRO_VERSION$(RESET)'
	@echo ''
	@echo '$(YELLOW)Version & migration:$(RESET)'
	@echo '  $(GREEN)make list$(RESET)              Discover projects and show pins vs RASA_PRO_VERSION'
	@echo '  $(GREEN)make status$(RESET)            Exit non-zero if any project drifts'
	@echo '  $(GREEN)make migrate$(RESET)           Bump pins, docs, and locks to RASA_PRO_VERSION'
	@echo '  $(GREEN)make migrate VERSION=x$(RESET) Bump to x and write RASA_PRO_VERSION'
	@echo ''
	@echo '$(YELLOW)Install & verify:$(RESET)'
	@echo '  $(GREEN)make lock-all$(RESET)          uv lock --prerelease=allow in every project'
	@echo '  $(GREEN)make install-all$(RESET)       uv sync --prerelease=allow in every project'
	@echo '  $(GREEN)make check-all$(RESET)         Sync + assert rasa-pro version + validate_project'
	@echo '  $(GREEN)make test-all$(RESET)          check-all, then rasa train when RASA_LICENSE is set'
	@echo '  $(GREEN)make verify-all$(RESET)        Per-project make verify (needs each project .env)'
	@echo '  $(GREEN)make clean-all$(RESET)         Per-project make clean'
	@echo ''
	@echo '$(YELLOW)Tips:$(RESET)'
	@echo '  KEEP_GOING=1           Continue after a project failure (report all)'
	@echo '  Docs:                  docs/MIGRATING.md'
	@echo ''

check-uv:
	@if [ -z "$(UV)" ]; then \
		echo "$(RED)✗ uv not found.$(RESET)"; \
		echo "$(YELLOW)  Install it:$(RESET) curl -LsSf https://astral.sh/uv/install.sh | sh"; \
		exit 1; \
	fi

_require-projects:
	@if [ -z "$(PROJECTS)" ]; then \
		echo "$(RED)✗ No projects discovered under examples/ or tutorials/.$(RESET)"; \
		exit 1; \
	fi

list: ## Show discovered projects and pin status
	@$(LIST) $(VERSION_ARGS)

status: ## Fail if any project drifts from RASA_PRO_VERSION
	@$(LIST) --status $(VERSION_ARGS)

migrate: check-uv ## Rewrite pins/docs/locks to RASA_PRO_VERSION (or VERSION=)
	@echo "$(BLUE)Migrating projects to rasa-pro $(if $(VERSION),$(VERSION),$$(cat $(ROOT)/RASA_PRO_VERSION))…$(RESET)"
	@$(MIGRATE) $(VERSION_ARGS)

lock-all: check-uv _require-projects ## Regenerate uv.lock in every project
	@fail=0; \
	for p in $(PROJECTS); do \
		echo "$(BLUE)→ lock $$p$(RESET)"; \
		if (cd $(ROOT)/$$p && $(UV) lock --prerelease=allow); then \
			echo "$(GREEN)✓ $$p$(RESET)"; \
		else \
			echo "$(RED)✗ $$p$(RESET)"; \
			fail=1; \
			if [ "$(KEEP_GOING)" != "1" ]; then exit 1; fi; \
		fi; \
	done; \
	exit $$fail

install-all: check-uv _require-projects ## uv sync in every project
	@fail=0; \
	for p in $(PROJECTS); do \
		echo "$(BLUE)→ install $$p$(RESET)"; \
		if (cd $(ROOT)/$$p && $(UV) sync --prerelease=allow); then \
			echo "$(GREEN)✓ $$p$(RESET)"; \
		else \
			echo "$(RED)✗ $$p$(RESET)"; \
			fail=1; \
			if [ "$(KEEP_GOING)" != "1" ]; then exit 1; fi; \
		fi; \
	done; \
	exit $$fail

check-all: check-uv _require-projects ## Sync + version assert + validate_project
	@fail=0; \
	for p in $(PROJECTS); do \
		if $(CHECK) $$p $(VERSION_ARGS); then \
			echo "$(GREEN)✓ check $$p$(RESET)"; \
		else \
			echo "$(RED)✗ check $$p$(RESET)"; \
			fail=1; \
			if [ "$(KEEP_GOING)" != "1" ]; then exit 1; fi; \
		fi; \
	done; \
	if [ $$fail -eq 0 ]; then echo "$(GREEN)All projects passed check-all.$(RESET)"; fi; \
	exit $$fail

test-all: check-uv _require-projects ## check-all + train when RASA_LICENSE is available
	@fail=0; \
	for p in $(PROJECTS); do \
		if $(CHECK) $$p --train $(VERSION_ARGS); then \
			echo "$(GREEN)✓ test $$p$(RESET)"; \
		else \
			echo "$(RED)✗ test $$p$(RESET)"; \
			fail=1; \
			if [ "$(KEEP_GOING)" != "1" ]; then exit 1; fi; \
		fi; \
	done; \
	if [ $$fail -eq 0 ]; then echo "$(GREEN)All projects passed test-all.$(RESET)"; fi; \
	exit $$fail

verify-all: check-uv _require-projects ## Delegate to each project's make verify
	@fail=0; \
	for p in $(PROJECTS); do \
		echo "$(BLUE)→ verify $$p$(RESET)"; \
		if $(MAKE) -C $(ROOT)/$$p verify; then \
			echo "$(GREEN)✓ $$p$(RESET)"; \
		else \
			echo "$(RED)✗ $$p$(RESET)"; \
			fail=1; \
			if [ "$(KEEP_GOING)" != "1" ]; then exit 1; fi; \
		fi; \
	done; \
	exit $$fail

clean-all: _require-projects ## Per-project make clean
	@for p in $(PROJECTS); do \
		echo "$(BLUE)→ clean $$p$(RESET)"; \
		$(MAKE) -C $(ROOT)/$$p clean; \
	done
	@echo "$(GREEN)✓ clean-all complete.$(RESET)"
