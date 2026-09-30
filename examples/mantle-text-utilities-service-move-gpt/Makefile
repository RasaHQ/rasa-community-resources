# Amber Grid home moves on GPT-5.5: a casebook case build (text, web chat)

UV     := $(shell command -v uv 2>/dev/null)
RASA   := uv run --locked rasa
REPO   := ../..
BUILD  := examples/mantle-text-utilities-service-move-gpt

.DEFAULT_GOAL := help
.PHONY: help install env proof proof-full validate train inspect run conversations metric clean

help: ## Show targets
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  make %-14s %s\n", $$1, $$2}'

install: ## Install the pinned rasa-pro into .venv
	uv sync --prerelease=allow

env: ## Create .env from .env.example (never overwrites)
	@test -f .env && echo ".env exists; left untouched" || (cp .env.example .env && echo "created .env; fill RASA_LICENSE and OPENAI_API_KEY")

proof: ## Offline guard tests (no licence, no model, no network; hook tests skip)
	python3 -m unittest discover -s tests -v

proof-full: ## The same tests in the project venv, including the output hook
	uv run --locked python -m unittest discover -s tests -v

validate: ## Mantle project validation
	uv run --locked python -c "from pathlib import Path; from rasa.mantle.validation import validate_project; validate_project(Path('.')); print('validate_project: ok')"

train: ## Package the agent model
	$(RASA) train

inspect: ## Chat with the agent in the Inspector
	$(RASA) inspect

run: ## Serve REST and socket.io web chat on port 5005
	$(RASA) run --enable-api

conversations: ## Live run of all scripted conversations (billed GPT-5.5 calls; cap 3.50 USD)
	python3 $(REPO)/scripts/case_builds/run_build.py $(BUILD) --budget-usd 3.5

metric: ## Case metric and receipt delivery for a recorded run: make metric RUN=<label>
	python3 case-build/case_metric.py case-build/results/$(RUN)

clean: ## Remove models and caches
	rm -rf models .rasa
	find . -name __pycache__ -type d -not -path './.venv/*' -exec rm -rf {} +
