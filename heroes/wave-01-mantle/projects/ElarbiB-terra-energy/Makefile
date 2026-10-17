# ==============================================================================
# Terra — TerraEnergy (Mantle agent, rasa-pro 3.20.0.dev6)
#
# One locked setup path from the project root: `uv sync` installs the Rasa
# agent AND the FastAPI backend from pyproject.toml + uv.lock. The Vite/React
# frontend is the only Node layer, installed with npm.
# ==============================================================================

GREEN   := $(shell tput -Txterm setaf 2 2>/dev/null)
YELLOW  := $(shell tput -Txterm setaf 3 2>/dev/null)
BLUE    := $(shell tput -Txterm setaf 4 2>/dev/null)
MAGENTA := $(shell tput -Txterm setaf 5 2>/dev/null)
RED     := $(shell tput -Txterm setaf 1 2>/dev/null)
RESET   := $(shell tput -Txterm sgr0 2>/dev/null)

UV     := $(shell command -v uv 2>/dev/null)
RUN    := uv run
PYTHON := $(RUN) python
RASA   := $(RUN) rasa

-include .env

.DEFAULT_GOAL := help

.PHONY: help check-uv env install install-voice verify validate train run inspect \
        backend frontend-install frontend test clean clean-all

help: ## Show this help message
	@echo ''
	@echo '$(MAGENTA)Terra — TerraEnergy (Mantle agent + FastAPI backend)$(RESET)'
	@echo ''
	@echo '$(YELLOW)First-time setup (in order):$(RESET)'
	@echo '  $(GREEN)make install$(RESET)         uv sync: Rasa agent + FastAPI backend (uv.lock)'
	@echo '  $(GREEN)make env$(RESET)             Create .env from .env.example (never overwrites)'
	@echo '  $(GREEN)make verify$(RESET)          Pre-flight check: keys, install, agent config'
	@echo '  $(GREEN)make train$(RESET)           Build (package) the agent model'
	@echo '  $(GREEN)make run$(RESET)             Start the Rasa REST server (port 5005)'
	@echo ''
	@echo '$(YELLOW)Optional layers:$(RESET)'
	@echo '  $(GREEN)make install-voice$(RESET)   Also install the local Whisper/Neuphonic voice deps'
	@echo '  $(GREEN)make backend$(RESET)         Start the FastAPI backend (port 8000)'
	@echo '  $(GREEN)make frontend-install$(RESET) Install the Vite/React frontend (npm)'
	@echo '  $(GREEN)make frontend$(RESET)        Start the frontend dev server (port 5173)'
	@echo ''
	@echo '$(YELLOW)Quality:$(RESET)'
	@echo '  $(GREEN)make validate$(RESET)        Validate the agent project (rasa.mantle.validate_project)'
	@echo '  $(GREEN)make inspect$(RESET)         Talk to the agent (Rasa Inspector)'
	@echo '  $(GREEN)make test$(RESET)            Backend pytest + frontend vitest'
	@echo ''

check-uv:
	@if [ -z "$(UV)" ]; then \
		echo "$(RED)✗ uv not found.$(RESET)"; \
		echo "$(YELLOW)  Install it:$(RESET) curl -LsSf https://astral.sh/uv/install.sh | sh"; \
		exit 1; \
	fi

env: ## Create .env from .env.example if it does not exist
	@if [ -f .env ]; then \
		echo "$(GREEN)✓ .env already exists — leaving it untouched.$(RESET)"; \
	else \
		cp .env.example .env; \
		echo "$(GREEN)✓ Created .env from .env.example$(RESET)"; \
		echo "$(YELLOW)  Fill in RASA_LICENSE and MISTRAL_API_KEY$(RESET)"; \
	fi

install: check-uv ## Install Rasa agent + FastAPI backend from uv.lock
	@echo "$(BLUE)Installing dependencies with uv...$(RESET)"
	$(UV) sync --prerelease=allow
	@echo "$(GREEN)✓ Dependencies installed into .venv.$(RESET)"
	@echo "$(YELLOW)  Next:$(RESET) make env && make verify"

install-voice: check-uv ## Also install the optional local voice dependencies
	$(UV) sync --prerelease=allow --extra voice
	@echo "$(GREEN)✓ Voice dependencies installed.$(RESET)"

verify: check-uv ## Run a pre-flight check of the setup
	@$(PYTHON) scripts/verify_setup.py

validate: check-uv ## Validate the agent project without training
	@echo "$(BLUE)Validating agent project...$(RESET)"
	@$(PYTHON) -c "from pathlib import Path; from rasa.mantle.validation import validate_project; validate_project(Path('.')); print('✓ project valid')"

train: check-uv ## Build (package) the agent model
	@echo "$(BLUE)Building the agent model...$(RESET)"
	$(RASA) train
	@echo "$(GREEN)✓ Model ready.$(RESET)  Next: $(GREEN)make run$(RESET)"

run: check-uv ## Start the Rasa REST server on port 5005
	$(RASA) run --enable-api --port 5005

inspect: check-uv ## Open the Rasa Inspector
	$(RASA) inspect

backend: check-uv ## Start the FastAPI backend on port 8000
	$(UV) run uvicorn main:app --app-dir backend --port 8000 --reload

frontend-install: ## Install the Vite/React frontend (npm)
	npm --prefix frontend install

frontend: ## Start the frontend dev server on port 5173
	npm --prefix frontend run dev

test: check-uv ## Run backend pytest and frontend vitest
	@echo "$(BLUE)Backend tests...$(RESET)"
	cd backend && $(PYTHON) -m pytest tests
	@echo "$(BLUE)Frontend tests...$(RESET)"
	npm --prefix frontend test

clean: ## Remove models, caches and build output
	@rm -rf models .rasa logs backend/cache frontend/dist
	@find . -name '__pycache__' -type d -not -path './.venv/*' -exec rm -rf {} + 2>/dev/null || true
	@echo "$(GREEN)✓ Clean complete.$(RESET)"

clean-all: clean ## Also remove the virtualenv
	@rm -rf .venv
	@echo "$(GREEN)✓ Removed .venv — run make install to start over.$(RESET)"