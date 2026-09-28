# ==============================================================================
# ☎️  Vela — Voice Banking on a Routed Vendor Stack (Rasa Mantle)
# ==============================================================================

# ------------------------------------------------------------------------------
# 🎨 Terminal colours
# ------------------------------------------------------------------------------
GREEN   := $(shell tput -Txterm setaf 2 2>/dev/null)
YELLOW  := $(shell tput -Txterm setaf 3 2>/dev/null)
BLUE    := $(shell tput -Txterm setaf 4 2>/dev/null)
MAGENTA := $(shell tput -Txterm setaf 5 2>/dev/null)
RED     := $(shell tput -Txterm setaf 1 2>/dev/null)
RESET   := $(shell tput -Txterm sgr0 2>/dev/null)

# ------------------------------------------------------------------------------
# 🛠️ Paths & runners
# ------------------------------------------------------------------------------
UV     := $(shell command -v uv 2>/dev/null)
RUN    := uv run
PYTHON := $(RUN) python
RASA   := $(RUN) rasa

# `.env` is included for presence checks inside Make only — it is deliberately
# NOT exported. Make keeps literal quotes on values, and rasa loads `.env` with
# `override=False`, so exporting here would shadow correctly parsed values.
# scripts/verify_setup.py (python-dotenv) is the authority on env parsing.
-include .env

.DEFAULT_GOAL := help

.PHONY: help check-uv env install verify validate train inspect run \
        guard-env show-demo-data drill stack clean clean-all

# ==============================================================================
# 📖 Help
# ==============================================================================
help: ## Show this help message
	@echo ''
	@echo '$(MAGENTA)☎️  Vela — Voice Banking on a Routed Vendor Stack (Rasa Mantle)$(RESET)'
	@echo ''
	@echo '$(YELLOW)First-time setup (in order):$(RESET)'
	@echo '  $(GREEN)make install$(RESET)          Install dependencies into .venv (uv)'
	@echo '  $(GREEN)make env$(RESET)              Create .env from .env.example (never overwrites)'
	@echo '  $(GREEN)make verify$(RESET)           Pre-flight check: keys, project, data, connectivity'
	@echo '  $(GREEN)make train$(RESET)            Build the agent model'
	@echo '  $(GREEN)make inspect$(RESET)          Talk to the agent (voice + text)'
	@echo ''
	@echo '$(YELLOW)Diagnostics:$(RESET)'
	@echo '  $(GREEN)make verify$(RESET)           Full pre-flight diagnostics (start here if stuck)'
	@echo '  $(GREEN)make validate$(RESET)         Fast skill/memory/tool validation only'
	@echo ''
	@echo '$(YELLOW)Run:$(RESET)'
	@echo '  $(GREEN)make inspect$(RESET)          Inspector UI — speak or type to Vela'
	@echo '  $(GREEN)make run$(RESET)              Start the agent API server on port 5005'
	@echo ''
	@echo '$(YELLOW)The routed voice stack:$(RESET)'
	@echo '  $(GREEN)make drill$(RESET)            Watch a vendor fail mid-call (no keys, no network)'
	@echo '  $(GREEN)make stack$(RESET)            List the voice stacks; STACK=<name> switches'
	@echo ''
	@echo '$(YELLOW)Demo data:$(RESET)'
	@echo '  $(GREEN)make show-demo-data$(RESET)   Print the demo accounts, cards, transactions'
	@echo ''
	@echo '$(YELLOW)Tutorial:$(RESET)'
	@echo ''
	@echo '$(YELLOW)Cleanup:$(RESET)'
	@echo '  $(GREEN)make clean$(RESET)            Remove models, caches, demo db'
	@echo '  $(GREEN)make clean-all$(RESET)        Also remove .venv (full reset)'
	@echo ''

# ==============================================================================
# 🚀 Setup
# ==============================================================================
check-uv:
	@if [ -z "$(UV)" ]; then \
		echo "$(RED)✗ uv not found.$(RESET)"; \
		echo "$(YELLOW)  Install it:$(RESET) curl -LsSf https://astral.sh/uv/install.sh | sh"; \
		echo "$(YELLOW)  Docs:$(RESET)       https://docs.astral.sh/uv/"; \
		exit 1; \
	fi

env: ## Create .env from .env.example if it does not exist
	@if [ -f .env ]; then \
		echo "$(GREEN)✓ .env already exists — leaving it untouched.$(RESET)"; \
	else \
		cp .env.example .env; \
		echo "$(GREEN)✓ Created .env from .env.example$(RESET)"; \
		echo "$(YELLOW)  Now open .env and fill in:$(RESET)"; \
		echo "    RASA_LICENSE      Rasa Pro Developer Edition license"; \
		echo "    OPENAI_API_KEY    LLM for routing and conversation"; \
		echo "    DEEPGRAM_API_KEY  First in the ASR chain, second in the TTS chain"; \
		echo "    RIME_API_KEY      Vela's own voice (optional — she falls back without it)"; \
	fi

install: check-uv ## Install all dependencies into .venv
	@echo "$(BLUE)Installing dependencies with uv...$(RESET)"
	$(UV) sync --prerelease=allow
	@echo "$(GREEN)✓ Dependencies installed.$(RESET)"
	@echo "$(YELLOW)  Next:$(RESET) make env && make verify"

guard-env:
	@if [ ! -f .env ]; then \
		echo "$(RED)✗ No .env file found.$(RESET)"; \
		echo "$(YELLOW)  Run:$(RESET) make env      (creates it from .env.example)"; \
		echo "$(YELLOW)  Then:$(RESET) make verify  (checks your keys)"; \
		exit 1; \
	fi

# ==============================================================================
# 🔍 Diagnostics
# ==============================================================================
verify: check-uv ## Run full pre-flight diagnostics
	@$(PYTHON) scripts/verify_setup.py

validate: check-uv guard-env ## Validate skills, memory, and tools (fast)
	@echo "$(BLUE)Validating agent project...$(RESET)"
	@$(PYTHON) -c "from pathlib import Path; from rasa.mantle.validation import validate_project; validate_project(Path('.')); print('OK')" \
		>/dev/null 2>&1 \
		&& echo "$(GREEN)✓ Project is valid.$(RESET)" \
		|| ( echo "$(RED)✗ Project validation failed. Details:$(RESET)"; \
		     $(PYTHON) -c "from pathlib import Path; from rasa.mantle.validation import validate_project; validate_project(Path('.'))" 2>&1 | grep -v '^20' | tail -40; \
		     exit 1 )

# ==============================================================================
# 🏋️ Build & run
# ==============================================================================
train: check-uv guard-env ## Validate and package the agent model
	@echo "$(BLUE)Training the agent...$(RESET)"
	$(RASA) train
	@echo "$(GREEN)✓ Model ready.$(RESET)  Next: $(GREEN)make inspect$(RESET)"

inspect: check-uv guard-env ## Open the Inspector (voice + text)
	@echo "$(MAGENTA)Opening the Inspector — use the mic for voice, or type.$(RESET)"
	$(RASA) inspect

run: check-uv guard-env ## Start the agent API server
	@echo "$(MAGENTA)Starting the agent on port 5005...$(RESET)"
	$(RASA) run --enable-api

# ==============================================================================
# 🔀 The routed voice stack
# ==============================================================================
# SCENARIO: credits | unreachable | rate-limit | bad-key   (default: all)
# STACK:    a file under stacks/, e.g. cost-tiered         (default: the live
#           integrations.yml)
drill: check-uv ## Replay a call with a vendor failing; print who speaks and why
	@$(PYTHON) scripts/drill_failover.py \
		$(if $(SCENARIO),--scenario $(SCENARIO),) \
		$(if $(STACK),--stack $(STACK),)

stack: ## List voice stacks, or switch to one with STACK=<name>
ifeq ($(STACK),)
	@echo '$(MAGENTA)Voice stacks$(RESET)  (stacks/README.md has the trade-offs)'
	@echo ''
	@matched=0; \
	for f in stacks/*.yml; do \
		name=$$(basename $$f .yml); \
		if cmp -s $$f integrations.yml; then \
			echo "  $(GREEN)* $$name  (current)$(RESET)"; matched=1; \
		else \
			echo "    $$name"; \
		fi; \
	done; \
	echo ''; \
	if [ $$matched -eq 0 ]; then \
		echo "$(YELLOW)  integrations.yml matches none of them — you have edited it.$(RESET)"; \
		echo "$(YELLOW)  Switching stacks would discard that; pass FORCE=1 if you mean to.$(RESET)"; \
		echo ''; \
	fi
	@echo '$(YELLOW)Switch:$(RESET) make stack STACK=offline'
else
	@if [ ! -f stacks/$(STACK).yml ]; then \
		echo "$(RED)✗ No such stack: stacks/$(STACK).yml$(RESET)"; \
		echo "$(YELLOW)  Run:$(RESET) make stack   (lists what there is)"; \
		exit 1; \
	fi
	@# An integrations.yml matching no stack file is one somebody edited on
	@# purpose, so switching would throw away work nobody asked to lose.
	@matched=0; \
	for f in stacks/*.yml; do cmp -s $$f integrations.yml && matched=1; done; \
	if [ $$matched -eq 0 ] && [ -z "$(FORCE)" ]; then \
		echo "$(RED)✗ integrations.yml matches no stack — refusing to overwrite it.$(RESET)"; \
		echo "$(YELLOW)  Keep your edits:$(RESET)    save them as stacks/<name>.yml first"; \
		echo "$(YELLOW)  Discard them:$(RESET)       make stack STACK=$(STACK) FORCE=1"; \
		exit 1; \
	fi
	@cp stacks/$(STACK).yml integrations.yml
	@echo "$(GREEN)✓ Now running the '$(STACK)' voice stack.$(RESET)"
	@echo "$(YELLOW)  See what it does:$(RESET) make drill"
endif

# ==============================================================================
# 🏦 Demo data
# ==============================================================================
show-demo-data: check-uv ## Print the demo customer's accounts, cards, and payees
	@$(PYTHON) scripts/show_demo_data.py

clean: ## Remove models, caches, and the generated demo db
	@echo "$(YELLOW)Cleaning build artefacts...$(RESET)"
	@rm -rf models .rasa logs
	@find . -name '__pycache__' -type d -not -path './.venv/*' -exec rm -rf {} + 2>/dev/null || true
	@find . -name '*.pyc' -not -path './.venv/*' -delete 2>/dev/null || true
	@echo "$(GREEN)✓ Clean complete.$(RESET)"

clean-all: clean ## Also remove the virtualenv (full reset)
	@rm -rf .venv
	@echo "$(GREEN)✓ Removed .venv — run $(RESET)make install$(GREEN) to start over.$(RESET)"
