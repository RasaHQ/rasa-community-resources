# ==============================================================================
# Artisan Roast — Voice & Conversational Coffee Shop Agent (Rasa Pro Mantle + Gemini)
# ==============================================================================

GREEN   := $(shell tput -Txterm setaf 2 2>/dev/null)
YELLOW  := $(shell tput -Txterm setaf 3 2>/dev/null)
BLUE    := $(shell tput -Txterm setaf 4 2>/dev/null)
MAGENTA := $(shell tput -Txterm setaf 5 2>/dev/null)
RED     := $(shell tput -Txterm setaf 1 2>/dev/null)
RESET   := $(shell tput -Txterm sgr0 2>/dev/null)

ROOT    := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
UV      := $(shell command -v uv 2>/dev/null)
RUN     := uv run
PYTHON  := $(RUN) python
RASA    := $(RUN) rasa

export PROJECT_ROOT := $(ROOT)
export PYTHONPATH := $(ROOT):$(PYTHONPATH)

-include .env

.DEFAULT_GOAL := help

.PHONY: help check-uv env install verify validate train inspect run \
        guard-env reset-db show-demo-data generate-data clean clean-all \
        test-e2e test-du test-judge test-coverage test-all

help: ## Show this help message
	@echo ''
	@echo '$(MAGENTA)Artisan Roast — Intelligent Coffee Shop AI Agent (Rasa Mantle)$(RESET)'
	@echo ''
	@echo '$(YELLOW)First-time setup (in order):$(RESET)'
	@echo '  $(GREEN)make install$(RESET)          Install dependencies into dedicated .venv (uv)'
	@echo '  $(GREEN)make env$(RESET)              Create .env from .env.example (never overwrites)'
	@echo '  $(GREEN)make reset-db$(RESET)         Generate datasets & ingest into SQLite database'
	@echo '  $(GREEN)make verify$(RESET)           Pre-flight diagnostics: keys, database, connectivity'
	@echo '  $(GREEN)make validate$(RESET)         Validate project structure and Mantle skills'
	@echo '  $(GREEN)make train$(RESET)            Validate & package the agent model'
	@echo '  $(GREEN)make inspect$(RESET)          Talk to Artisan Roast (voice + text Inspector)'
	@echo ''
	@echo '$(YELLOW)Demo data & Database:$(RESET)'
	@echo '  $(GREEN)make generate-data$(RESET)    Synthesize customers, BOM costs & store inventory'
	@echo '  $(GREEN)make show-demo-data$(RESET)   Print sample customers, store inventory & menu items'
	@echo '  $(GREEN)make reset-db$(RESET)         Re-ingest all tables into data/coffeeshop.db'
	@echo ''
	@echo '$(YELLOW)Testing & Evaluation:$(RESET)'
	@echo '  $(GREEN)make test-e2e$(RESET)         Run deterministic E2E flow and slot assertions'
	@echo '  $(GREEN)make test-du$(RESET)          Run Dialogue Understanding command generation tests'
	@echo '  $(GREEN)make test-judge$(RESET)       Run LLM-as-a-Judge groundedness tests'
	@echo '  $(GREEN)make test-coverage$(RESET)    Generate test flow coverage report'
	@echo '  $(GREEN)make test-all$(RESET)         Run all evaluation instruments'
	@echo ''
	@echo '$(YELLOW)Runtime & Maintenance:$(RESET)'
	@echo '  $(GREEN)make run$(RESET)              Start the agent API server'
	@echo '  $(GREEN)make clean$(RESET)            Clean cache, db, and model artifacts'
	@echo '  $(GREEN)make clean-all$(RESET)        Clean everything including .venv'
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
		echo "$(YELLOW)  Fill in RASA_LICENSE, GEMINI_API_KEY, and DEEPGRAM_API_KEY$(RESET)"; \
	fi

install: check-uv ## Install all dependencies into .venv
	@echo "$(BLUE)Installing dependencies with uv...$(RESET)"
	$(UV) sync --prerelease=allow
	@echo "$(GREEN)✓ Dependencies installed.$(RESET)"
	@echo "$(YELLOW)  Next:$(RESET) make reset-db"

guard-env:
	@if [ ! -f .env ]; then \
		echo "$(RED)✗ No .env file found.$(RESET)"; \
		echo "$(YELLOW)  Run:$(RESET) make env"; \
		exit 1; \
	fi

generate-data: check-uv ## Generate synthetic customer, recipe and inventory datasets
	@echo "$(BLUE)Generating synthetic customer, raw material, and inventory datasets...$(RESET)"
	@$(PYTHON) scripts/generate_datasets.py

reset-db: check-uv generate-data ## Reseed SQLite DB from datasets
	@echo "$(BLUE)Ingesting tables into data/coffeeshop.db...$(RESET)"
	@$(PYTHON) lib/importer.py

show-demo-data: check-uv ## Print demo accounts, inventory, and menu
	@$(PYTHON) scripts/show_demo_data.py

verify: check-uv guard-env ## Run full pre-flight diagnostics
	@export SSL_CERT_FILE=$$($(PYTHON) -c "import certifi; print(certifi.where())" 2>/dev/null) || true; \
	$(PYTHON) scripts/verify_setup.py

validate: check-uv guard-env ## Validate skills and project structure
	@echo "$(BLUE)Validating Artisan Roast agent project...$(RESET)"
	@$(PYTHON) scripts/validate_project.py

train: check-uv guard-env ## Validate and package the agent model
	@echo "$(BLUE)Training & packaging Artisan Roast agent model...$(RESET)"
	@export SSL_CERT_FILE=$$($(PYTHON) -c "import certifi; print(certifi.where())" 2>/dev/null) || true; \
	$(RASA) train
	@echo "$(GREEN)✓ Model ready.$(RESET)  Next: $(GREEN)make inspect$(RESET)"

inspect: check-uv guard-env ## Open the Inspector (voice + text)
	@echo "$(MAGENTA)Opening Artisan Roast Inspector — use microphone or chat.$(RESET)"
	@export SSL_CERT_FILE=$$($(PYTHON) -c "import certifi; print(certifi.where())" 2>/dev/null) || true; \
	$(RASA) inspect

run: check-uv guard-env ## Start the agent API server
	@export SSL_CERT_FILE=$$($(PYTHON) -c "import certifi; print(certifi.where())" 2>/dev/null) || true; \
	$(RASA) run --enable-api

test-e2e: check-uv guard-env ## Run fast deterministic E2E tracker assertions
	@echo "$(BLUE)Running deterministic E2E assertions...$(RESET)"
	@export SSL_CERT_FILE=$$($(PYTHON) -c "import certifi; print(certifi.where())" 2>/dev/null) || true; \
	$(RASA) test e2e tests/e2e/test_deterministic.yml

test-du: check-uv guard-env ## Run Dialogue Understanding (DU) command generator tests
	@echo "$(BLUE)Running Dialogue Understanding (DU) command tests...$(RESET)"
	@export SSL_CERT_FILE=$$($(PYTHON) -c "import certifi; print(certifi.where())" 2>/dev/null) || true; \
	export RASA_PRO_BETA_DIALOGUE_UNDERSTANDING_TEST=true; \
	$(RASA) test du tests/dialogue_understanding/

test-judge: check-uv guard-env ## Run LLM-as-a-Judge assertions for FAQ responses
	@echo "$(BLUE)Running LLM-as-a-Judge groundedness & relevance tests...$(RESET)"
	@export SSL_CERT_FILE=$$($(PYTHON) -c "import certifi; print(certifi.where())" 2>/dev/null) || true; \
	$(RASA) test e2e tests/e2e/test_judge_faq.yml

test-coverage: check-uv guard-env ## Generate test flow coverage report
	@echo "$(BLUE)Generating E2E flow coverage report...$(RESET)"
	@export SSL_CERT_FILE=$$($(PYTHON) -c "import certifi; print(certifi.where())" 2>/dev/null) || true; \
	$(RASA) test e2e tests/e2e/ --coverage-report

test-sim: check-uv guard-env ## Run multi-turn agent evaluation simulator
	@echo "$(BLUE)Running multi-turn agent evaluation simulator...$(RESET)"
	$(PYTHON) evals/eval_simulator.py

test-all: test-e2e test-du test-judge test-coverage test-sim ## Run all evaluation instruments


clean: ## Remove models, caches, and database
	@rm -rf models .rasa logs data/coffeeshop.db
	@find . -name '__pycache__' -type d -not -path './.venv/*' -exec rm -rf {} + 2>/dev/null || true
	@echo "$(GREEN)✓ Clean complete.$(RESET)"

clean-all: clean ## Also remove the virtualenv
	@rm -rf .venv
	@echo "$(GREEN)✓ Removed .venv — run make install to start over.$(RESET)"
