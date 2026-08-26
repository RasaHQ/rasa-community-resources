# ==============================================================================
# ☎️  Vela — Voice Banking on Speechmatics ASR (Rasa Mantle)
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
        guard-env show-demo-data clean clean-all

# ==============================================================================
# 📖 Help
# ==============================================================================
help: ## Show this help message
	@echo ''
	@echo '$(MAGENTA)☎️  Vela — Voice Banking on Speechmatics ASR (Rasa Mantle)$(RESET)'
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
		echo "    DEEPGRAM_API_KEY  Speech-to-text AND text-to-speech"; \
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
	@$(PYTHON) -c "from pathlib import Path; from rasa.calm_v2.validation import validate_project; validate_project(Path('.')); print('OK')" \
		>/dev/null 2>&1 \
		&& echo "$(GREEN)✓ Project is valid.$(RESET)" \
		|| ( echo "$(RED)✗ Project validation failed. Details:$(RESET)"; \
		     $(PYTHON) -c "from pathlib import Path; from rasa.calm_v2.validation import validate_project; validate_project(Path('.'))" 2>&1 | grep -v '^20' | tail -40; \
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
