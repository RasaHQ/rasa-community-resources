# ==============================================================================
# NourishHer — Voice Nutrition Companion (Rasa Skills + Deepgram)
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

.PHONY: help check-uv env install verify validate train inspect run api ui test e2e e2e-coverage guard-env clean clean-all

# Ports (override on the command line: make api API_PORT=5015)
API_PORT ?= 5011
UI_PORT  ?= 8080

help: ## Show this help message
	@echo ''
	@echo '$(MAGENTA)NourishHer — Voice Nutrition Companion (Rasa Skills + Deepgram)$(RESET)'
	@echo ''
	@echo '$(YELLOW)First-time setup (in order):$(RESET)'
	@echo '  $(GREEN)make install$(RESET)   Install dependencies into .venv (uv)'
	@echo '  $(GREEN)make env$(RESET)       Create .env from .env.example (never overwrites)'
	@echo '  $(GREEN)make verify$(RESET)    Pre-flight check: keys, project structure, connectivity'
	@echo '  $(GREEN)make train$(RESET)     Build the agent model'
	@echo '  $(GREEN)make inspect$(RESET)   Talk to NourishHer (voice + text)'
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
		echo "$(YELLOW)  Fill in RASA_LICENSE, GROQ_API_KEY, GEMINI_API_KEY, DEEPGRAM_API_KEY$(RESET)"; \
	fi

install: check-uv ## Install all dependencies into .venv
	@echo "$(BLUE)Installing dependencies with uv...$(RESET)"
	$(UV) sync --prerelease=allow
	@echo "$(GREEN)✓ Dependencies installed.$(RESET)"
	@echo "$(YELLOW)  Next:$(RESET) make env && make verify"

guard-env:
	@if [ ! -f .env ]; then \
		echo "$(RED)✗ No .env file found.$(RESET)"; \
		echo "$(YELLOW)  Run:$(RESET) make env"; \
		exit 1; \
	fi

verify: check-uv ## Run full pre-flight diagnostics
	@$(PYTHON) scripts/verify_setup.py

validate: check-uv guard-env ## Validate skills and print every finding
	@echo "$(BLUE)Validating agent project...$(RESET)"
	@$(PYTHON) scripts/validate_project.py

train: check-uv guard-env ## Validate and package the agent model
	@echo "$(BLUE)Training the agent...$(RESET)"
	$(RASA) train
	@echo "$(GREEN)✓ Model ready.$(RESET)  Next: $(GREEN)make inspect$(RESET)"

inspect: check-uv guard-env ## Open the Inspector (voice + text)
	@echo "$(MAGENTA)Opening the Inspector — use the mic for voice, or type.$(RESET)"
	$(RASA) inspect

run: check-uv guard-env ## Start the agent API server
	$(RASA) run --enable-api

api: check-uv guard-env ## Start the API server with CORS enabled (for the web UI)
	@echo "$(MAGENTA)API on http://localhost:$(API_PORT) (CORS enabled)$(RESET)"
	$(RASA) run --enable-api --cors "*" --port $(API_PORT)

ui: ## Serve the embedded web UI (run `make api` in another terminal first)
	@echo "$(MAGENTA)Web UI on http://localhost:$(UI_PORT)  →  open it in your browser$(RESET)"
	@echo "$(YELLOW)  (needs the API running: make api)$(RESET)"
	@$(PYTHON) -m http.server $(UI_PORT) --directory ui

test: check-uv ## Run the deterministic persistence/tool test suite (no LLM/network)
	@echo "$(BLUE)Running deterministic tests...$(RESET)"
	@$(RUN) python -m unittest discover -s tests -v

e2e: check-uv guard-env ## Run the Rasa e2e conversation eval harness (drives the live LLM)
	@echo "$(BLUE)Running Rasa e2e eval harness...$(RESET)"
	@$(RASA) test e2e tests/e2e_test_cases.yml

e2e-coverage: check-uv guard-env ## e2e eval harness + flow/command coverage report
	@echo "$(BLUE)Running Rasa e2e eval harness with coverage...$(RESET)"
	@$(RASA) test e2e tests/e2e_test_cases.yml --coverage-report --coverage-output-path e2e_coverage

clean: ## Remove models, caches, and logs
	@rm -rf models .rasa logs
	@find . -name '__pycache__' -type d -not -path './.venv/*' -exec rm -rf {} + 2>/dev/null || true
	@echo "$(GREEN)✓ Clean complete.$(RESET)"

clean-all: clean ## Also remove the virtualenv
	@rm -rf .venv
	@echo "$(GREEN)✓ Removed .venv — run make install to start over.$(RESET)"
