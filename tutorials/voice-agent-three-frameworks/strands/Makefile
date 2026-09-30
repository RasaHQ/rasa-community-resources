# concern: ops
# The AWS Strands Agents version of the Cedar Clinic voice agent (one of three).
# Speech is Speechmatics in and out; the model is GPT-5.5 at reasoning effort low.

TUTORIAL := ..
SERVER := uv run --locked python server.py
# Keys for `make run`: this folder's .env, if any, exported into the server only.
WITH_ENV := set -a; if [ -f .env ]; then . ./.env; fi; set +a;

.DEFAULT_GOAL := help
.PHONY: help install env test run web spec spec-text count clean

help: ## Show targets
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  make %-10s %s\n", $$1, $$2}'

install: ## Install strands-agents and the shared cedar_clinic and cedar_speech packages into .venv
	uv sync --locked

env: ## Create .env from .env.example (never overwrites)
	@test -f .env && echo ".env exists; left untouched" || (cp .env.example .env && echo "created .env; fill the two keys")

test: ## Offline tests: parity with the shared parts, the guard, the protocol, concern tags
	uv run --locked python -m unittest discover -s tests -v

run: ## Serve browser_audio at ws://localhost:5007/webhooks/browser_audio/websocket
	$(WITH_ENV) $(SERVER) --port 5007

web: ## The shared voice page on http://127.0.0.1:8765/, relaying to :5007
	python3 $(TUTORIAL)/shared/web/serve.py strands

spec: ## The shared spec over browser audio (billed: GPT-5.5 and Speechmatics; cap 4 USD across runs)
	python3 $(TUTORIAL)/shared/spec/run_spec.py strands --server-cmd "$(SERVER) --port {port}" --budget-usd 4

spec-text: ## The same calls as typed turns (skips speech-to-text; still billed)
	python3 $(TUTORIAL)/shared/spec/run_spec.py strands --server-cmd "$(SERVER) --port {port}" --mode text \
		--budget-usd 4 --label text

count: ## Lines per concern (plus shared/speech, the voice adapter), and the guard diff
	python3 $(TUTORIAL)/shared/spec/count_concerns.py .
	python3 $(TUTORIAL)/shared/spec/count_concerns.py $(TUTORIAL)/shared/speech
	python3 $(TUTORIAL)/shared/spec/count_concerns.py . --diff

clean: ## Remove caches
	find . -name __pycache__ -type d -not -path './.venv/*' -exec rm -rf {} +
