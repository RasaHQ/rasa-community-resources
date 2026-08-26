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
DIM     := $(shell tput -Txterm dim 2>/dev/null)
RESET   := $(shell tput -Txterm sgr0 2>/dev/null)

PYTHON  ?= python3
UV      := $(shell command -v uv 2>/dev/null)
ROOT    := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
SCRIPTS := $(ROOT)/scripts

# Optional override: make migrate VERSION=3.19.0.dev7
VERSION ?=
# KEEP_GOING=1 continues after a project failure (check-all / test-all / lock-all / …)
KEEP_GOING ?= 0
# STRICT=1 promotes lint warnings to failures.
STRICT ?= 0
# REQUIRE_LICENSE=1 makes a missing RASA_LICENSE a failure instead of a skip.
# Without it, test-all silently passes while training nothing.
REQUIRE_LICENSE ?= 0
# REQUIRE_SECRETS=1 does the same for the provider keys a resource declares in
# [tool.rasa-catalog] required-secrets. Off by default because CI legitimately
# lacks them; on when you want "trained everything" to mean it.
REQUIRE_SECRETS ?= 0

VERSION_ARGS := $(if $(VERSION),--version $(VERSION),)
STRICT_ARGS  := $(if $(filter 1,$(STRICT)),--strict,)
LICENSE_ARGS := $(if $(filter 1,$(REQUIRE_LICENSE)),--require-license,)
SECRET_ARGS  := $(if $(filter 1,$(REQUIRE_SECRETS)),--require-secrets,)
LIST         := $(PYTHON) $(SCRIPTS)/list_projects.py
MIGRATE      := $(PYTHON) $(SCRIPTS)/migrate_rasa_pro.py
CHECK        := $(PYTHON) $(SCRIPTS)/check_project.py
LINT         := $(PYTHON) $(SCRIPTS)/lint_repo.py
UNITTESTS    := $(PYTHON) $(SCRIPTS)/test_tooling.py

# The maintained catalog: examples/, tutorials/, patterns/. These move together
# under `make migrate` and must stay green.
PROJECTS := $(shell $(LIST) --paths-only 2>/dev/null)
# Frozen snapshots: community/, heroes/. Pinned by their authors, never
# migrated, checked against their own pins. See docs/SNAPSHOTS.md.
SNAPSHOTS := $(shell $(LIST) --scope snapshots --paths-only 2>/dev/null)
# Empty for a stable pin; --prerelease=allow only when RASA_PRO_VERSION is a
# dev/rc build. Derived so the flag can never drift from the pin.
PRE      := $(shell $(LIST) --uv-prerelease-args 2>/dev/null)

.DEFAULT_GOAL := help

.PHONY: help check-uv list status outdated update migrate migrate-dry latest \
        lint test-scripts validate ci validate-full \
        lock-all install-all check-all test-all verify-all clean-all \
        snapshots check-snapshots \
        _require-projects

help: ## Show this help message
	@echo ''
	@echo '$(MAGENTA)Rasa Community Resources$(RESET) — runnable Rasa Pro examples and tutorials'
	@echo ""
	@echo "  Pinned to:    $(GREEN)$$(cat $(ROOT)/RASA_PRO_VERSION)$(RESET)   $(DIM)(RASA_PRO_VERSION)$(RESET)"
	@echo "  Release line: $(GREEN)$$(if [ -f $(ROOT)/RASA_PRO_VERSION_LINE ]; then grep -v '^#' $(ROOT)/RASA_PRO_VERSION_LINE | grep -v '^$$' | head -1; else echo 'none — any release allowed'; fi)$(RESET)   $(DIM)(RASA_PRO_VERSION_LINE)$(RESET)"
	@echo "  Projects:     $(GREEN)$(words $(PROJECTS))$(RESET) maintained   $(DIM)+ $(words $(SNAPSHOTS)) frozen snapshot(s) in community/ and heroes/$(RESET)"
	@echo ''
	@echo '$(BLUE)══ Read this first ═══════════════════════════════════════════════$(RESET)'
	@echo ''
	@if [ -f $(ROOT)/RASA_PRO_VERSION_LINE ]; then \
		echo '  $(RED)The newest rasa-pro on PyPI is usually NOT the one to pin.$(RESET)'; \
		echo ''; \
		echo '  Every resource here imports $(YELLOW)rasa.calm_v2$(RESET) (the Mantle engine),'; \
		echo '  which ships only on the release line above. The newest stable'; \
		echo '  release does not contain it, so pinning "latest" would break all'; \
		echo '  $(words $(PROJECTS)) projects at import time.'; \
		echo ''; \
		echo '  You do not have to remember this. The tooling enforces it:'; \
		echo '  $(GREEN)make outdated$(RESET) tells you the truth, and $(GREEN)make migrate$(RESET) refuses a'; \
		echo '  release that lacks the engine. $(RED)Never hand-edit RASA_PRO_VERSION.$(RESET)'; \
	else \
		echo '  No release line is configured, so $(GREEN)make latest$(RESET) tracks the newest'; \
		echo '  stable rasa-pro on PyPI. That is the normal state.'; \
		echo ''; \
		echo '  $(RED)Never hand-edit RASA_PRO_VERSION$(RESET) — use $(GREEN)make update$(RESET), which also'; \
		echo '  rewrites the docs and re-resolves every uv.lock.'; \
	fi
	@echo ''
	@echo '$(BLUE)══ Keeping the catalog up to date (do these in order) ════════════$(RESET)'
	@echo ''
	@echo '  $(GREEN)1. make outdated$(RESET)       Ask PyPI what is new. Safe, read-only.'
	@echo '  $(GREEN)2. make update$(RESET)         Bump to the newest USABLE release, then re-check.'
	@echo '  $(GREEN)3. make ci$(RESET)             Install all $(words $(PROJECTS)) projects for real and validate them.'
	@echo '  $(GREEN)4. make validate-full$(RESET)  Also train every agent. Needs RASA_LICENSE.'
	@echo '  $(GREEN)5.$(RESET) Bump the same pin in the $(YELLOW)rasa-community$(RESET) website repo'
	@echo '     ($(GREEN)make sync-rasa-version$(RESET) there) so the tutorials agree.'
	@echo ''
	@echo '  $(DIM)Nothing to do if step 1 says the pin is newest on the line.$(RESET)'
	@echo '  $(DIM)If it says the line can be lifted, follow the instructions it prints.$(RESET)'
	@echo ''
	@echo '$(YELLOW)▸ Version & migration$(RESET)'
	@echo '  $(GREEN)make list$(RESET)              Show every project and its pin vs RASA_PRO_VERSION'
	@echo '  $(GREEN)make status$(RESET)            Exit non-zero if any project has drifted'
	@echo '  $(GREEN)make outdated$(RESET)          Newest on our line AND newest overall, with the reason'
	@echo '  $(GREEN)make update$(RESET)            outdated + latest + validate (the routine bump)'
	@echo '  $(GREEN)make latest$(RESET)            Bump to the newest release on the supported line'
	@echo '  $(GREEN)make migrate$(RESET)           Rewrite pins, docs and locks to RASA_PRO_VERSION'
	@echo '  $(GREEN)make migrate VERSION=x$(RESET) Bump to x (refuses x if it lacks the engine)'
	@echo '  $(GREEN)make migrate-dry VERSION=x$(RESET) Preview a bump; writes nothing'
	@echo ''
	@echo '$(YELLOW)▸ Validate (cheapest first)$(RESET)'
	@echo '  $(GREEN)make validate$(RESET)          Offline gate: unit tests + lint + drift (~2s)'
	@echo '  $(GREEN)make ci$(RESET)                validate + install every project + validate_project'
	@echo '  $(GREEN)make validate-full$(RESET)     ci + rasa train everywhere (needs RASA_LICENSE)'
	@echo '  $(GREEN)make lint$(RESET)              Static checks only ($(GREEN)--json$(RESET) via scripts/lint_repo.py)'
	@echo '  $(GREEN)make test-scripts$(RESET)      Unit-test the tooling'
	@echo ''
	@echo '$(YELLOW)▸ Two tiers (docs/SNAPSHOTS.md)$(RESET)'
	@echo '  $(DIM)Maintained:$(RESET) examples/ tutorials/ patterns/ — one shared pin, migrated together'
	@echo '  $(DIM)Frozen:$(RESET)     community/ heroes/     — author-pinned, never migrated'
	@echo '  $(GREEN)make snapshots$(RESET)         List frozen resources and the pin each one carries'
	@echo '  $(GREEN)make check-snapshots$(RESET)   Install each frozen resource against its own pin'
	@echo ''
	@echo '$(YELLOW)▸ Install & run$(RESET)'
	@echo '  $(GREEN)make lock-all$(RESET)          uv lock in every project'
	@echo '  $(GREEN)make install-all$(RESET)       uv sync in every project'
	@echo '  $(GREEN)make check-all$(RESET)         Sync + assert rasa-pro version + validate_project'
	@echo '  $(GREEN)make test-all$(RESET)          check-all, then rasa train when RASA_LICENSE is set'
	@echo '  $(GREEN)make verify-all$(RESET)        Per-project make verify (needs each project .env)'
	@echo '  $(GREEN)make clean-all$(RESET)         Per-project make clean'
	@echo ''
	@echo '$(YELLOW)▸ Switches$(RESET)'
	@echo '  $(GREEN)KEEP_GOING=1$(RESET)           Continue after a project fails, report them all'
	@echo '  $(GREEN)STRICT=1$(RESET)               Promote lint warnings to failures (CI uses this)'
	@echo '  $(GREEN)REQUIRE_LICENSE=1$(RESET)      Fail rather than skip when RASA_LICENSE is absent'
	@echo '  $(GREEN)REQUIRE_SECRETS=1$(RESET)      Same for declared provider keys (Gemini, etc.)'
	@echo ''
	@echo '$(YELLOW)▸ When something fails$(RESET)'
	@echo '  $(GREEN)make validate$(RESET) names the check and the fix for every finding.'
	@echo '  Version/lock drift  → $(GREEN)make migrate$(RESET)'
	@echo '  "does not ship rasa.calm_v2" → you targeted a release off the line;'
	@echo '                        run $(GREEN)make outdated$(RESET) and read what it says.'
	@echo '  Docs: $(GREEN)docs/VALIDATION.md$(RESET) (what each check means)'
	@echo '        $(GREEN)docs/MIGRATING.md$(RESET) (version bumps and release lines)'
	@echo ''

check-uv:
	@if [ -z "$(UV)" ]; then \
		echo "$(RED)✗ uv not found.$(RESET)"; \
		echo "$(YELLOW)  Install it:$(RESET) curl -LsSf https://astral.sh/uv/install.sh | sh"; \
		exit 1; \
	fi

_require-projects:
	@if [ -z "$(PROJECTS)" ]; then \
		echo "$(RED)✗ No projects discovered under examples/, tutorials/ or patterns/.$(RESET)"; \
		exit 1; \
	fi

list: ## Show discovered projects and pin status
	@$(LIST) $(VERSION_ARGS)

status: ## Fail if any project drifts from RASA_PRO_VERSION
	@$(LIST) --status $(VERSION_ARGS)

outdated: ## Report whether PyPI has a newer rasa-pro than the pin
	@$(LIST) --check-latest $(VERSION_ARGS)

migrate: check-uv ## Rewrite pins/docs/locks to RASA_PRO_VERSION (or VERSION=)
	@echo "$(BLUE)Migrating projects to rasa-pro $(if $(VERSION),$(VERSION),$$(cat $(ROOT)/RASA_PRO_VERSION))…$(RESET)"
	@$(MIGRATE) $(VERSION_ARGS)

migrate-dry: ## Preview a migration; writes nothing and never runs uv lock
	@$(MIGRATE) $(VERSION_ARGS) --dry-run

latest: check-uv ## Bump to the newest rasa-pro on the supported release line
	@$(MIGRATE) --latest

update: check-uv ## The routine bump: what is new, take it if usable, re-validate
	@$(MAKE) --no-print-directory outdated
	@echo ''
	@echo "$(MAGENTA)▸ bumping to the newest usable release$(RESET)"
	@$(MAKE) --no-print-directory latest
	@echo ''
	@$(MAKE) --no-print-directory validate
	@echo ''
	@echo "$(YELLOW)Next: 'make ci' to prove every project still installs and validates.$(RESET)"
	@echo "$(YELLOW)Then bump the website repo too: (cd ../rasa-community && make sync-rasa-version)$(RESET)"

# ==============================================================================
# Validation
# ==============================================================================
# Three layers, cheapest first. Each is independently runnable; `validate` is
# the offline gate, `ci` adds real installs, `validate-full` adds training.
#
#   lint          static consistency   ~1s   no network, no uv, no venv
#   test-scripts  tooling unit tests   ~1s   no network, no uv, no venv
#   status        pin/lock drift       ~1s   no network
#   check-all     install + validate   ~min  needs uv + network
#   test-all      + rasa train         ~min  needs a real RASA_LICENSE
# ==============================================================================

lint: ## Static checks: versions, locks, skill prose, metadata, secrets
	@$(LINT) $(STRICT_ARGS) $(VERSION_ARGS)

test-scripts: ## Unit-test the migration/lint tooling
	@$(UNITTESTS)

validate: ## Offline correctness gate (lint + unit tests + drift). Start here.
	@echo "$(MAGENTA)▸ tooling unit tests$(RESET)"
	@out=$$($(UNITTESTS) 2>&1) || { echo "$$out"; exit 1; }; \
		case "$$out" in *"OK"*) ;; *) echo "$$out"; \
			echo "$(RED)✗ unit tests produced no OK line — suite did not run.$(RESET)"; \
			exit 1;; esac; \
		echo "$$out" | tail -3
	@echo ''
	@echo "$(MAGENTA)▸ repository lint$(RESET)"
	@$(LINT) $(STRICT_ARGS) $(VERSION_ARGS)
	@echo ''
	@echo "$(MAGENTA)▸ pin / lock drift$(RESET)"
	@$(LIST) --status $(VERSION_ARGS)
	@echo ''
	@echo "$(GREEN)✓ validate passed — repository is internally consistent.$(RESET)"
	@echo "$(YELLOW)  Note: this does not install anything. Run 'make ci' for that.$(RESET)"

ci: validate check-all check-snapshots ## validate + install every resource, both tiers
	@echo "$(GREEN)✓ ci passed — every resource installs and validates.$(RESET)"

validate-full: validate ## Everything, including rasa train (needs RASA_LICENSE)
	@$(MAKE) test-all REQUIRE_LICENSE=1 KEEP_GOING=$(KEEP_GOING)
	@echo "$(GREEN)✓ validate-full passed — every resource trains end to end.$(RESET)"

lock-all: check-uv _require-projects ## Regenerate uv.lock in every project
	@fail=0; \
	for p in $(PROJECTS); do \
		echo "$(BLUE)→ lock $$p$(RESET)"; \
		if (cd $(ROOT)/$$p && $(UV) lock $(PRE)); then \
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
		if (cd $(ROOT)/$$p && $(UV) sync $(PRE)); then \
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

snapshots: ## List frozen snapshots (community/, heroes/) and their own pins
	@$(LIST) --scope snapshots

check-snapshots: check-uv ## Install every frozen snapshot and run validate_project
	@if [ -z "$(SNAPSHOTS)" ]; then \
		echo "$(DIM)No frozen snapshots checked in yet.$(RESET)"; \
		exit 0; \
	fi; \
	fail=0; \
	for p in $(SNAPSHOTS); do \
		if $(CHECK) $$p --use-project-pin; then \
			echo "$(GREEN)✓ check $$p$(RESET)"; \
		else \
			echo "$(RED)✗ check $$p$(RESET)"; \
			fail=1; \
			if [ "$(KEEP_GOING)" != "1" ]; then exit 1; fi; \
		fi; \
	done; \
	if [ $$fail -eq 0 ]; then echo "$(GREEN)All frozen snapshots still install and validate.$(RESET)"; fi; \
	exit $$fail

test-all: check-uv _require-projects ## check-all + train when RASA_LICENSE is available
	@fail=0; \
	for p in $(PROJECTS); do \
		if $(CHECK) $$p --train $(LICENSE_ARGS) $(SECRET_ARGS) $(VERSION_ARGS); then \
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
