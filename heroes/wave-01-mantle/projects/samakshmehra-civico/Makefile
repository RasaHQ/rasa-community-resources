# ==============================================================================
# Civico — voice agent for a municipal complaint line (Rasa Mantle + Deepgram)
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

.PHONY: help check-uv env install verify test train inspect run demo-call eval \
        guard-env reset-db show-demo-data demo-failure demo-unknown clean clean-all

help: ## Show this help message
	@echo ''
	@echo '$(MAGENTA)Civico — voice agent for a municipal complaint line$(RESET)'
	@echo ''
	@echo '$(YELLOW)First time, in order:$(RESET)'
	@echo '  $(GREEN)make install$(RESET)          Install dependencies into .venv (uv)'
	@echo '  $(GREEN)make env$(RESET)              Create .env from .env.example (never overwrites)'
	@echo '  $(GREEN)make verify$(RESET)           Pre-flight: keys, project, skills, data'
	@echo '  $(GREEN)make test$(RESET)             Run the offline tool/database test suite'
	@echo '  $(GREEN)make eval$(RESET)             How to run the conversation scenarios'
	@echo '  $(GREEN)make train$(RESET)            Validate and package the model'
	@echo '  $(GREEN)make inspect$(RESET)          Talk to it — voice or text'
	@echo ''
	@echo '$(YELLOW)Demo:$(RESET)'
	@echo '  $(GREEN)make show-demo-data$(RESET)   Print the ward directory and seeded complaints'
	@echo '  $(GREEN)make demo-call$(RESET)        Replay a scripted call — ARGS=report|status|duplicate|…'
	@echo '  $(GREEN)make demo-unknown$(RESET)     Inspector as an unrecognised caller'
	@echo '  $(GREEN)make demo-failure$(RESET)     Inspector with the register forced to fail'
	@echo '  $(GREEN)make reset-db$(RESET)         Reseed the demo database from data/'
	@echo ''

check-uv:
	@if [ -z "$(UV)" ]; then \
		echo "$(RED)✗ uv not found.$(RESET)"; \
		echo "$(YELLOW)  Install it:$(RESET) curl -LsSf https://astral.sh/uv/install.sh | sh"; \
		exit 1; \
	fi

env: ## Create .env from .env.example if it does not exist
	@if [ -e .env ]; then \
		echo "$(GREEN)✓ .env already exists — leaving it untouched.$(RESET)"; \
	else \
		cp .env.example .env; \
		echo "$(GREEN)✓ Created .env from .env.example$(RESET)"; \
		echo "$(YELLOW)  Fill in RASA_LICENSE, OPENAI_API_KEY, DEEPGRAM_API_KEY$(RESET)"; \
	fi

install: check-uv ## Install all dependencies into .venv
	@echo "$(BLUE)Installing dependencies with uv...$(RESET)"
	$(UV) sync --prerelease=allow
	@echo "$(GREEN)✓ Dependencies installed.$(RESET)  Next: $(GREEN)make env && make verify$(RESET)"

guard-env:
	@if [ ! -e .env ]; then \
		echo "$(RED)✗ No .env file found.$(RESET)"; \
		echo "$(YELLOW)  Run:$(RESET) make env"; \
		exit 1; \
	fi

verify: check-uv ## Run pre-flight diagnostics
	@$(PYTHON) scripts/verify_setup.py

test: check-uv ## Run the offline test suite (no network, no LLM)
	@$(PYTHON) -m unittest discover -s tests -v

.PHONY: quality
quality: check-uv ## Read-only conversation scorecard; ARGS='--sender ID --server http://localhost:5007'
	@$(PYTHON) scripts/conversation_quality.py $(ARGS)

train: check-uv guard-env ## Validate and package the model
	@echo "$(BLUE)Training...$(RESET)"
	$(RASA) train
	@echo "$(GREEN)✓ Model ready.$(RESET)  Next: $(GREEN)make inspect$(RESET)"

inspect: check-uv guard-env ## Open the Inspector (voice + text)
	@echo "$(MAGENTA)Opening the Inspector — use the mic for voice, or type.$(RESET)"
	$(RASA) inspect

run: check-uv guard-env ## Start the agent API server
	$(RASA) run --enable-api -p 5007

demo-call: check-uv ## Replay a scripted call against a running agent (needs `make run`)
	@$(PYTHON) scripts/demo_call.py $(ARGS)

eval: check-uv guard-env ## How to run the conversation scenarios (needs the MCP server)
	@echo "$(MAGENTA)Simulation scenarios are driven through the Rasa MCP server.$(RESET)"
	@echo ""
	@echo "  1. $(GREEN)make run$(RESET)                            the agent, on :5007"
	@echo "  2. $(GREEN)uv run rasa tools run --mode stdio$(RESET)  the MCP server, another shell"
	@echo "  3. ask your coding agent: $(YELLOW)\"run all scenarios in eval/scenarios/\"$(RESET)"
	@echo ""
	@echo "$(YELLOW)Reset the register between scenarios — filing and escalating mutate it:$(RESET)"
	@echo "  $(GREEN)make reset-db$(RESET)   (works while the agent is running)"
	@echo ""
	@echo "$(YELLOW)A single run is not a verdict.$(RESET) The caller and the judge are both"
	@echo "LLMs. Use a run_count of 3 or more before believing a failure —"
	@echo "see $(GREEN)eval/README.md$(RESET)."
	@echo ""

show-demo-data: check-uv ## Print the ward directory and seeded complaints
	@$(PYTHON) scripts/show_demo_data.py

demo-unknown: check-uv guard-env ## Inspector as a caller the line does not recognise
	@echo "$(YELLOW)Calling from an unrecognised number — no name, no history.$(RESET)"
	CIVICO_DEMO_CALLER=9000000000 $(RASA) inspect

demo-failure: check-uv guard-env ## Inspector with file_complaint forced to fail
	@echo "$(YELLOW)file_complaint will fail — this demonstrates on_failure.$(RESET)"
	CIVICO_FORCE_FILE_FAILURE=1 $(RASA) inspect

reset-db: ## Delete the demo database so it reseeds from data/
	@rm -f data/civico.db
	@echo "$(GREEN)✓ Database reset — it reseeds on the next tool call.$(RESET)"

clean: ## Remove models, caches and the generated database
	@rm -rf models .rasa logs data/civico.db
	@find . -name '__pycache__' -type d -not -path './.venv/*' -exec rm -rf {} + 2>/dev/null || true
	@echo "$(GREEN)✓ Clean complete.$(RESET)"

clean-all: clean ## Also remove the virtualenv
	@rm -rf .venv
	@echo "$(GREEN)✓ Removed .venv — run make install to start over.$(RESET)"
