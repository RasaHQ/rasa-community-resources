# ==============================================================================
# voice-auth-stepup — risk-tiered authentication step-up
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

.DEFAULT_GOAL := help

.PHONY: help check-uv install env test test-e2e prove train inspect clean

help: ## Show this help message
	@echo ''
	@echo '$(MAGENTA)voice-auth-stepup$(RESET) — auth strength as a function of the action'
	@echo ''
	@echo '$(YELLOW)Setup:$(RESET)'
	@echo '  $(GREEN)make install$(RESET)     Install dependencies into .venv (uv)'
	@echo '  $(GREEN)make env$(RESET)         Create .env from .env.example (never overwrites)'
	@echo ''
	@echo '$(YELLOW)The eval suite:$(RESET)'
	@echo '  $(GREEN)make test$(RESET)        Guard tests. No model, no network, no keys.'
	@echo '  $(GREEN)make prove$(RESET)       Delete the guard, watch the suite go red, restore it.'
	@echo '  $(GREEN)make test-e2e$(RESET)    Conversation tests (needs a trained model + keys)'
	@echo ''
	@echo '$(YELLOW)Run it:$(RESET)'
	@echo '  $(GREEN)make train$(RESET)       Build the agent model'
	@echo '  $(GREEN)make inspect$(RESET)     Talk to the agent'
	@echo ''

check-uv:
	@if [ -z "$(UV)" ]; then \
		echo "$(RED)uv not found.$(RESET) curl -LsSf https://astral.sh/uv/install.sh | sh"; \
		exit 1; \
	fi

install: check-uv ## Install dependencies
	@$(UV) sync --prerelease=allow

env: ## Create .env from the example, never overwriting an existing one
	@if [ -f .env ]; then echo "$(YELLOW).env already exists — leaving it alone.$(RESET)"; \
	else cp .env.example .env; echo "$(GREEN)Created .env — fill in the values.$(RESET)"; fi

test: check-uv ## Guard tests: no model, no network, no credentials
	@$(PYTHON) -m unittest discover -s tests -v

# ==============================================================================
# The one target worth reading the Makefile for.
# ==============================================================================
# A guard nobody has watched fail is a docstring. This deletes the tier check
# from reissue_card, runs the suite, and asserts it FAILS — then restores the
# file and asserts it passes again. If the suite stays green with the guard
# gone, the negative test is decorative and this target says so loudly.
prove: check-uv ## Prove the load-bearing test actually fails without the guard
	@$(PYTHON) scripts/prove_guard.py

test-e2e: check-uv ## Conversation tests (needs a trained model and API keys)
	@$(RASA) test e2e tests/e2e/

train: check-uv ## Build the agent model
	@$(RASA) train

inspect: check-uv ## Talk to the agent
	@$(RASA) inspect

clean: ## Remove build artifacts
	@rm -rf models/ .rasa/ __pycache__ */__pycache__ .banking.py.orig
	@echo "$(GREEN)cleaned$(RESET)"
