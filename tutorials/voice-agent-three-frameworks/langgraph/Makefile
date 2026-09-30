# concern: ops
# The LangGraph version of the Cedar Clinic voice agent (one of three).
# Speech is Speechmatics in and out; the model is GPT-5.5 at reasoning_effort low.

TUTORIAL := ..
PORT ?= 5006
# Keys: this folder's .env, else the repository root's (never printed).
ENV_FILE := $(firstword $(wildcard .env ../../../.env))
SERVER := uv run --locked python server.py

.DEFAULT_GOAL := help
.PHONY: help install env test run spec spec-text web count clean

help: ## Show targets
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  make %-10s %s\n", $$1, $$2}'

install: ## Install langgraph, langchain, langchain-openai and the shared packages into .venv
	uv sync --locked

env: ## Create .env from .env.example (never overwrites)
	@test -f .env && echo ".env exists; left untouched" || (cp .env.example .env && echo "created .env; fill the two keys")

test: ## Offline tests: parity with the shared parts, the guard, the voice loop (scripted model, fake TTS)
	uv run --locked python -m unittest discover -s tests -v

run: ## Serve browser_audio at ws://localhost:5006/webhooks/browser_audio/websocket (keys from .env)
	uv run --locked $(if $(ENV_FILE),--env-file $(ENV_FILE),) python server.py --port $(PORT)

spec: ## The shared spec over browser audio (billed: GPT-5.5 and Speechmatics; cap 4 USD across runs)
	python3 $(TUTORIAL)/shared/spec/run_spec.py langgraph --server-cmd "$(SERVER) --port {port}" --budget-usd 4

spec-text: ## The same calls as typed turns (skips speech-to-text; still billed)
	python3 $(TUTORIAL)/shared/spec/run_spec.py langgraph --server-cmd "$(SERVER) --port {port}" --mode text --budget-usd 4 --label text

web: ## The shared voice page on http://127.0.0.1:8765/, relaying to :5006
	python3 $(TUTORIAL)/shared/web/serve.py langgraph

count: ## Lines per concern, and the guard diff
	python3 $(TUTORIAL)/shared/spec/count_concerns.py .
	python3 $(TUTORIAL)/shared/spec/count_concerns.py . --diff

clean: ## Remove caches
	find . -name __pycache__ -type d -not -path './.venv/*' -exec rm -rf {} +
