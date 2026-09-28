# ==============================================================================
# Wren — guarding an irreversible action (card reissue)
# ==============================================================================
# `make policy` is the target worth knowing: it exercises the guard with no
# model, no licence, and no network, and prints what it refused and why.
# ==============================================================================
GREEN  := $(shell tput -Txterm setaf 2 2>/dev/null)
YELLOW := $(shell tput -Txterm setaf 3 2>/dev/null)
RED    := $(shell tput -Txterm setaf 1 2>/dev/null)
DIM    := $(shell tput -Txterm dim 2>/dev/null)
RESET  := $(shell tput -Txterm sgr0 2>/dev/null)

UV     := $(shell command -v uv 2>/dev/null)
PYTHON ?= python3

.DEFAULT_GOAL := help
.PHONY: help check-uv env guard-env install validate train chat run policy clean

help: ## Show this help message
	@echo ''
	@echo '$(YELLOW)Wren — guarding an irreversible action$(RESET)'
	@echo ''
	@echo '  $(GREEN)make env$(RESET)        Create .env from .env.example'
	@echo '  $(GREEN)make install$(RESET)    Install dependencies (uv sync --prerelease=allow)'
	@echo '  $(GREEN)make policy$(RESET)     Exercise the guard — no licence or network needed'
	@echo '  $(GREEN)make validate$(RESET)   Validate the project without training'
	@echo '  $(GREEN)make train$(RESET)      Train the agent'
	@echo '  $(GREEN)make chat$(RESET)       Talk to the agent in the Inspector'
	@echo '  $(GREEN)make clean$(RESET)      Remove models and caches'
	@echo ''
	@echo '$(DIM)  Walkthrough: my card was stolen, I need a new one$(RESET)'
	@echo '$(DIM)              send it to 9 Elsewhere Lane, Leeds, LS1 9ZZ$(RESET)'
	@echo '$(DIM)              -> refused: a stated address needs a one-time code$(RESET)'
	@echo ''

check-uv:
	@if [ -z "$(UV)" ]; then \
		echo "$(RED)✗ uv not found.$(RESET)  curl -LsSf https://astral.sh/uv/install.sh | sh"; \
		exit 1; \
	fi

env: ## Create .env from .env.example if it does not exist
	@if [ -f .env ]; then echo "$(YELLOW).env already exists — leaving it alone.$(RESET)"; \
	else cp .env.example .env; echo "$(GREEN)✓ .env created — add RASA_LICENSE, OPENAI_API_KEY, DEEPGRAM_API_KEY.$(RESET)"; fi

guard-env:
	@if [ ! -f .env ]; then echo "$(RED)✗ No .env — run: make env$(RESET)"; exit 1; fi

install: check-uv ## Install dependencies
	@$(UV) sync --prerelease=allow

policy: ## Exercise the guard directly — no licence, no model, no network
	@$(PYTHON) scripts/prove_guard.py

validate: check-uv guard-env ## Validate the project without training
	@$(UV) run python -c "from pathlib import Path; from rasa.mantle.validation import validate_project; validate_project(Path('.'))" \
		&& echo "$(GREEN)✓ Project is valid.$(RESET)"

train: check-uv guard-env ## Train the agent
	@$(UV) run rasa train

chat: check-uv guard-env ## Talk to the agent in the Inspector
	@$(UV) run rasa inspect

run: check-uv guard-env ## Start the API server
	@$(UV) run rasa run --enable-api

clean: ## Remove models and caches
	@rm -rf models .rasa
	@find . -name __pycache__ -type d -prune -exec rm -rf {} + 2>/dev/null || true
	@echo "$(GREEN)✓ cleaned$(RESET)"
