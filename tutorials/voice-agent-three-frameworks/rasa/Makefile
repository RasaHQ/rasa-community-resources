# concern: ops
# The Rasa Mantle version of the Cedar Clinic voice agent (one of three).
# Speech is Speechmatics in and out; the model is GPT-5.5 at reasoning_effort low.

RASA := uv run --locked rasa
TUTORIAL := ..

.DEFAULT_GOAL := help
.PHONY: help install env test validate train run inspect spec spec-text web count clean

help: ## Show targets
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  make %-10s %s\n", $$1, $$2}'

install: ## Install rasa-pro and the shared cedar_clinic package into .venv
	uv sync --prerelease=allow --locked

env: ## Create .env from .env.example (never overwrites)
	@test -f .env && echo ".env exists; left untouched" || (cp .env.example .env && echo "created .env; fill the three keys")

test: ## Offline tests: parity with the shared parts, guard configuration, Speechmatics message parity
	uv run --locked python -m unittest discover -s tests -v

validate: ## Mantle project validation
	uv run --locked python -c "from pathlib import Path; from rasa.mantle.validation import validate_project; validate_project(Path('.')); print('validate_project: ok')"

train: ## Package the agent model
	$(RASA) train

run: ## Serve browser_audio at ws://localhost:5005/webhooks/browser_audio/websocket (and the API)
	$(RASA) run --enable-api -p 5005

inspect: ## Talk to it in the Rasa Inspector
	$(RASA) inspect

spec: ## The shared spec over browser audio (billed: GPT-5.5 and Speechmatics; cap 4 USD across runs)
	python3 $(TUTORIAL)/shared/spec/run_spec.py rasa --budget-usd 4

spec-text: ## The same calls as typed turns (skips speech-to-text; still billed)
	python3 $(TUTORIAL)/shared/spec/run_spec.py rasa --mode text --budget-usd 4 --label text

web: ## The shared voice page on http://127.0.0.1:8765/, relaying to :5005
	python3 $(TUTORIAL)/shared/web/serve.py rasa

count: ## Lines per concern, and the guard diff
	python3 $(TUTORIAL)/shared/spec/count_concerns.py .
	python3 $(TUTORIAL)/shared/spec/count_concerns.py . --diff

clean: ## Remove models and caches
	rm -rf models .rasa
	find . -name __pycache__ -type d -not -path './.venv/*' -exec rm -rf {} +
