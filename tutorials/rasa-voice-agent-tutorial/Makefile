# ==============================================================================
# Atlas — Voice Travel Agent (Rasa Skills + Deepgram)
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

.PHONY: help check-uv env install verify validate train inspect run \
        guard-env reset-db show-demo-data tutorial clean clean-all

help: ## Show this help message
	@echo ''
	@echo '$(MAGENTA)Atlas — Voice Travel Agent (Rasa Skills + Deepgram)$(RESET)'
	@echo ''
	@echo '$(YELLOW)First-time setup (in order):$(RESET)'
	@echo '  $(GREEN)make install$(RESET)          Install dependencies into .venv (uv)'
	@echo '  $(GREEN)make env$(RESET)              Create .env from .env.example (never overwrites)'
	@echo '  $(GREEN)make verify$(RESET)           Pre-flight check: keys, project, data, connectivity'
	@echo '  $(GREEN)make train$(RESET)            Build the agent model'
	@echo '  $(GREEN)make inspect$(RESET)          Talk to the agent (voice + text)'
	@echo ''
	@echo '$(YELLOW)Demo data:$(RESET)'
	@echo '  $(GREEN)make show-demo-data$(RESET)   Print Maya Chen bookings and flights'
	@echo '  $(GREEN)make reset-db$(RESET)         Reseed the demo travel DB from data/source/'
	@echo ''
	@echo '$(YELLOW)Tutorial:$(RESET)'
	@echo '  $(GREEN)make tutorial$(RESET)         Show chapters and snippet paths'
	@echo '  Full walkthrough: https://rasa.community/library/tutorials/voice-ai-agent/'
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
		echo "$(YELLOW)  Fill in RASA_LICENSE, OPENAI_API_KEY, DEEPGRAM_API_KEY$(RESET)"; \
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

show-demo-data: check-uv ## Print the demo traveler's bookings and flights
	@$(PYTHON) scripts/show_demo_data.py

reset-db: ## Delete the demo travel DB so it reseeds from data/source/
	@rm -f data/travel.db
	@echo "$(GREEN)✓ Demo travel DB reset — it will reseed on the next tool call.$(RESET)"

tutorial: ## Show the live-session chapters and where the snippets live
	@echo ''
	@echo '$(MAGENTA)Build a voice AI agent with Rasa Skills$(RESET)'
	@echo ''
	@echo 'Hosted tutorial: https://rasa.community/library/tutorials/voice-ai-agent/'
	@echo ''
	@echo '$(YELLOW)Paste-ready snippets:$(RESET)'
	@echo '  $(GREEN)0$(RESET)  Scaffold                         tutorial/snippets/step-00-scaffold/'
	@echo '  $(GREEN)1$(RESET)  FAQ skill                        tutorial/snippets/step-01-faq/'
	@echo '  $(GREEN)2$(RESET)  First tool (itinerary)           tutorial/snippets/step-02-itinerary/'
	@echo '  $(GREEN)3$(RESET)  Tool constraints                 tutorial/snippets/step-03-constraints/'
	@echo '  $(GREEN)4$(RESET)  Scoped instructions              tutorial/snippets/step-04-scoped/'
	@echo '  $(GREEN)5$(RESET)  Verbatim + ordered baggage       tutorial/snippets/step-05-baggage/'
	@echo '  $(GREEN)6$(RESET)  Composition (change booking)     tutorial/snippets/step-06-composition/'
	@echo '  $(GREEN)7$(RESET)  Remaining skills                 tutorial/snippets/step-07-remaining/'
	@echo ''

clean: ## Remove models, caches, and the generated demo db
	@rm -rf models .rasa logs data/travel.db
	@find . -name '__pycache__' -type d -not -path './.venv/*' -exec rm -rf {} + 2>/dev/null || true
	@echo "$(GREEN)✓ Clean complete.$(RESET)"

clean-all: clean ## Also remove the virtualenv
	@rm -rf .venv
	@echo "$(GREEN)✓ Removed .venv — run make install to start over.$(RESET)"
