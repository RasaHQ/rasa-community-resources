# ==============================================================================
# 📄 rasa-document-artifact-tutorial — the document is DERIVED, never written
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

.PHONY: help check-uv env install guard-env prove test render diff validate \
        train inspect chat run clean clean-all

help: ## Show this help message
	@echo ''
	@echo '$(MAGENTA)📄 rasa-document-artifact-tutorial$(RESET)'
	@echo '$(YELLOW)   The conversation edits state. The document is derived from it.$(RESET)'
	@echo ''
	@echo '$(YELLOW)No credentials needed (start here):$(RESET)'
	@echo '  $(GREEN)make prove$(RESET)            The four proof cases — no licence, no model, no network'
	@echo '  $(GREEN)make render$(RESET)           Derive the document and print it'
	@echo '  $(GREEN)make diff$(RESET)             Change one field and show what moved in the document'
	@echo '  $(GREEN)make test$(RESET)             Eval suite'
	@echo ''
	@echo '$(YELLOW)First-time setup (in order):$(RESET)'
	@echo '  $(GREEN)make install$(RESET)          Install dependencies into .venv (uv)'
	@echo '  $(GREEN)make env$(RESET)              Create .env from .env.example (never overwrites)'
	@echo '  $(GREEN)make validate$(RESET)         Validate skills, memory, and tools'
	@echo '  $(GREEN)make train$(RESET)            Build the agent model'
	@echo '  $(GREEN)make chat$(RESET)             Talk to the agent'
	@echo ''
	@echo '$(YELLOW)Cleanup:$(RESET)'
	@echo '  $(GREEN)make clean$(RESET)            Remove models, caches, rendered documents'
	@echo '  $(GREEN)make clean-all$(RESET)        Also remove .venv (full reset)'
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
		echo "$(YELLOW)  Now open .env and fill in RASA_LICENSE and OPENAI_API_KEY$(RESET)"; \
	fi

install: check-uv ## Install all dependencies into .venv
	@echo "$(BLUE)Installing dependencies with uv...$(RESET)"
	$(UV) sync --prerelease=allow
	@echo "$(GREEN)✓ Dependencies installed.$(RESET)"

guard-env:
	@if [ ! -f .env ]; then \
		echo "$(RED)✗ No .env file found.$(RESET)"; \
		echo "$(YELLOW)  Run:$(RESET) make env"; \
		exit 1; \
	fi

# ==============================================================================
# 🔍 The proof and the demos — bare python3, no venv, no credentials, no network
# ==============================================================================
prove: ## The four proof cases: traceable, refuses, idempotent, one-field diff
	@python3 scripts/prove_derivation.py

render: ## Derive the document from fixture state and print it
	@python3 scripts/render_document.py

diff: ## Change one field and show exactly what moved in the document
	@python3 scripts/render_document.py --diff

test: ## Eval suite
	@python3 -m unittest discover -s tests -v

# ==============================================================================
# 🏋️ Build & run
# ==============================================================================
validate: check-uv guard-env ## Validate skills, memory, and tools (fast)
	@echo "$(BLUE)Validating agent project...$(RESET)"
	@$(PYTHON) -c "from pathlib import Path; from rasa.mantle.validation import validate_project; validate_project(Path('.')); print('OK')" \
		>/dev/null 2>&1 \
		&& echo "$(GREEN)✓ Project is valid.$(RESET)" \
		|| ( echo "$(RED)✗ Project validation failed. Details:$(RESET)"; \
		     $(PYTHON) -c "from pathlib import Path; from rasa.mantle.validation import validate_project; validate_project(Path('.'))" 2>&1 | grep -v '^20' | tail -40; \
		     exit 1 )

train: check-uv guard-env ## Validate and package the agent model
	@echo "$(BLUE)Training the agent...$(RESET)"
	$(RASA) train
	@echo "$(GREEN)✓ Model ready.$(RESET)  Next: $(GREEN)make chat$(RESET)"

inspect: check-uv guard-env ## Open the Inspector
	$(RASA) inspect

chat: inspect ## Talk to the agent (alias for inspect)

run: check-uv guard-env ## Start the agent API server
	$(RASA) run --enable-api

clean: ## Remove models, caches, and rendered documents
	@echo "$(YELLOW)Cleaning build artefacts...$(RESET)"
	@rm -rf models .rasa logs
	@rm -f out/*.md
	@find . -name '__pycache__' -type d -not -path './.venv/*' -exec rm -rf {} + 2>/dev/null || true
	@find . -name '*.pyc' -not -path './.venv/*' -delete 2>/dev/null || true
	@echo "$(GREEN)✓ Clean complete.$(RESET)"

clean-all: clean ## Also remove the virtualenv (full reset)
	@rm -rf .venv
	@echo "$(GREEN)✓ Removed .venv — run $(RESET)make install$(GREEN) to start over.$(RESET)"
