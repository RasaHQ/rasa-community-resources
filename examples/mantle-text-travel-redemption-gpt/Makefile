# Horizon Rewards redemption on GPT-5.5: a casebook case build (text, web chat)

UV     := $(shell command -v uv 2>/dev/null)
RASA   := uv run --locked rasa
REPO   := ../..

.DEFAULT_GOAL := help
.PHONY: help install env proof validate train inspect run conversations clean

help: ## Show targets
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  make %-14s %s\n", $$1, $$2}'

install: ## Install the pinned rasa-pro into .venv
	uv sync --prerelease=allow

env: ## Create .env from .env.example (never overwrites)
	@test -f .env && echo ".env exists; left untouched" || (cp .env.example .env && echo "created .env; fill RASA_LICENSE and OPENAI_API_KEY")

proof: ## Offline guard tests (no licence, no model, no network)
	python3 -m unittest discover -s tests -v

validate: ## Mantle project validation
	uv run --locked python -c "from pathlib import Path; from rasa.mantle.validation import validate_project; validate_project(Path('.')); print('validate_project: ok')"

train: ## Package the agent model
	$(RASA) train

inspect: ## Chat with the agent in the Inspector
	$(RASA) inspect

run: ## Serve REST and socket.io web chat on port 5005
	$(RASA) run --enable-api

conversations: ## Live run of all scripted conversations (billed OpenAI calls; cap 3.50 USD)
	python3 $(REPO)/scripts/case_builds/run_build.py examples/mantle-text-travel-redemption-gpt --budget-usd 3.5

clean: ## Remove models and caches
	rm -rf models .rasa
	find . -name __pycache__ -type d -not -path './.venv/*' -exec rm -rf {} +
