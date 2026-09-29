# Northgate dispute intake on Claude Sonnet 5.5 with Speechmatics and Rime: a casebook case build (browser voice)

UV     := $(shell command -v uv 2>/dev/null)
RASA   := uv run --locked rasa
REPO   := ../..
BUILD  := examples/mantle-voice-banking-dispute-claude

.DEFAULT_GOAL := help
.PHONY: help install env proof validate train inspect run caller-audio conversations dry-run clean

help: ## Show targets
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  make %-14s %s\n", $$1, $$2}'

install: ## Install the pinned rasa-pro into .venv
	uv sync --prerelease=allow

env: ## Create .env from .env.example (never overwrites)
	@test -f .env && echo ".env exists; left untouched" || (cp .env.example .env && echo "created .env; fill RASA_LICENSE, ANTHROPIC_API_KEY, SPEECHMATICS_API_KEY and RIME_API_KEY")

proof: ## Offline guard tests (no licence, no model, no network)
	python3 -m unittest discover -s tests -v

validate: ## Mantle project validation
	uv run --locked python -c "from pathlib import Path; from rasa.mantle.validation import validate_project; validate_project(Path('.')); print('validate_project: ok')"

train: ## Package the agent model
	$(RASA) train

inspect: ## Talk to the agent in the Inspector (microphone; Speechmatics in, Rime out)
	$(RASA) inspect

run: ## Serve the browser_audio WebSocket (and the API) on port 5005
	$(RASA) run --enable-api

caller-audio: ## Render missing caller WAVs with OpenAI gpt-4o-mini-tts, Indian English accent instructed (billed per token)
	python3 $(REPO)/scripts/case_builds/render_caller_audio.py $(BUILD) --budget-usd 4.5

conversations: ## Live voice run of every scripted call (billed Claude, Speechmatics and Rime; cap 4.50 USD)
	python3 $(REPO)/scripts/case_builds/run_build.py $(BUILD) --budget-usd 4.5

dry-run: ## Same calls with {"text"} frames: skips speech-to-text, still bills Claude and Rime
	python3 $(REPO)/scripts/case_builds/run_build.py $(BUILD) --budget-usd 4.5 --voice-mode text --label dry-run

clean: ## Remove models and caches
	rm -rf models .rasa
	find . -name __pycache__ -type d -not -path './.venv/*' -exec rm -rf {} +
