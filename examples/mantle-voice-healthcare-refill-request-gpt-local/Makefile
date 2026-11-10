# Cedar Clinic refill requests on GPT-5.5, speech on the Mac: a casebook case build (browser voice)
#
# Speech-to-text (faster-whisper) and text-to-speech (NeuTTS on Metal) run on
# this machine. Only the model call goes to OpenAI.

UV     := $(shell command -v uv 2>/dev/null)
RASA   := uv run --locked rasa
REPO   := ../..
BUILD  := examples/mantle-voice-healthcare-refill-request-gpt-local
NEUTTS := $(REPO)/patterns/voice-vendor-router/native/neutts
WHISPER_MODEL ?= small.en
# Where prepare_models.py looks for NeuTTS files you already have (it checks digests).
NEUTTS_FROM ?= $(HOME)/models/neutts

.DEFAULT_GOAL := help
.PHONY: help install env native voice-models whisper-model neutts-models proof validate train inspect run caller-audio conversations dry-run clean

help: ## Show targets
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  make %-14s %s\n", $$1, $$2}'

install: ## Install the pinned rasa-pro and faster-whisper into .venv
	uv sync --prerelease=allow

env: ## Create .env from .env.example (never overwrites)
	@test -f .env && echo ".env exists; left untouched" || (cp .env.example .env && echo "created .env; fill RASA_LICENSE and OPENAI_API_KEY")

native: ## Build llama.cpp (Metal) and the NeuCodec decoder from pinned sources
	$(NEUTTS)/build.sh

voice-models: whisper-model neutts-models ## Put both local speech models in place, digest-checked

whisper-model: ## Download the faster-whisper model into .whisper/ (once; calls never download)
	uv run --locked python -c "from faster_whisper import download_model; print(download_model('$(WHISPER_MODEL)', output_dir='.whisper/$(WHISPER_MODEL)'))"

neutts-models: ## Verify and link the NeuTTS-2E files (NEUTTS_FROM=dir), or HF_TOKEN=... to download them
	@if [ -n "$$HF_TOKEN" ]; then python3 $(NEUTTS)/prepare_models.py --fetch; \
	else python3 $(NEUTTS)/prepare_models.py --from "$(NEUTTS_FROM)"; fi

proof: ## Offline guard tests (no licence, no model, no network)
	python3 -m unittest discover -s tests -v

validate: ## Mantle project validation
	uv run --locked python -c "from pathlib import Path; from rasa.mantle.validation import validate_project; validate_project(Path('.')); print('validate_project: ok')"

train: ## Package the agent model
	$(RASA) train

inspect: ## Talk to the agent in the Inspector (microphone; faster-whisper in, NeuTTS out)
	$(RASA) inspect

run: ## Serve the browser_audio WebSocket (and the API) on port 5005
	$(RASA) run --enable-api

caller-audio: ## Render missing caller WAVs with Deepgram Aura-2 (billed per character)
	python3 $(REPO)/scripts/case_builds/render_caller_audio.py $(BUILD) --budget-usd 4.5

conversations: ## Live voice run of every scripted call (billed GPT-5.5 only; cap 4.50 USD)
	python3 $(REPO)/scripts/case_builds/run_build.py $(BUILD) --budget-usd 4.5

dry-run: ## Same calls with {"text"} frames: skips speech-to-text, still bills the model
	python3 $(REPO)/scripts/case_builds/run_build.py $(BUILD) --budget-usd 4.5 --voice-mode text --label dry-run

clean: ## Remove models and caches (keeps .whisper/)
	rm -rf models .rasa
	find . -name __pycache__ -type d -not -path './.venv/*' -exec rm -rf {} +
