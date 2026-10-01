# The same Cedar Clinic voice agent on Rasa Mantle, LangGraph and AWS Strands Agents.
# Shared parts in shared/; one folder per framework. See README.md and COMPARISON-PLAN.md.

.DEFAULT_GOAL := help
.PHONY: help test test-clinic test-spec test-speech test-speech-deepgram speech-live web count rasa-variant spec-rasa-variant spec-deepgram

help: ## Show targets
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  make %-12s %s\n", $$1, $$2}'

test: test-clinic test-spec test-speech test-speech-deepgram ## Offline tests of the shared parts (bare python3 and uv; no network)

test-clinic: ## cedar_clinic: rules, tools, audit log
	cd shared/clinic && python3 -m unittest discover -s tests -v

test-spec: ## The spec's checks, guard invariant, LLM meter and spec file
	python3 -m unittest discover -s shared/spec/tests -v

test-speech: ## cedar_speech: Speechmatics messages, reply handling, audio (offline)
	cd shared/speech && uv run --python 3.12 python -m unittest tests.test_offline -v

test-speech-deepgram: ## cedar_speech_deepgram: query, turn joining, TTS messages, the launcher (offline)
	cd shared/speech && uv run --python 3.12 python -m unittest discover -s ../speech-deepgram/tests -v

speech-live: ## One live Speechmatics round trip (billed: a few seconds of realtime audio)
	cd shared/speech && uv run --python 3.12 python -m unittest tests.test_live -v

web: ## The voice page on http://127.0.0.1:8765/, relaying to the Rasa version on :5005
	python3 shared/web/serve.py rasa

# Variants: the same agents on other speech settings, for the latency comparison.
# They leave rasa/, langgraph/ and strands/ (and their counted lines) unchanged.
VARIANT ?= deepgram-tts
LABEL ?= $(shell date -u +%Y%m%dT%H%M%S)
BUDGET ?= 4
PRICES_deepgram-tts := speechmatics-stt-deepgram-tts
PRICES_deepgram := deepgram

rasa-variant: ## Copy rasa/ to rasa-$(VARIANT)/ with variants/rasa-$(VARIANT).integrations.yml (VARIANT=deepgram-tts|deepgram)
	rm -rf rasa-$(VARIANT)
	rsync -a --exclude .venv --exclude models --exclude .rasa --exclude __pycache__ --exclude '.env' rasa/ rasa-$(VARIANT)/
	cp variants/rasa-$(VARIANT).integrations.yml rasa-$(VARIANT)/integrations.yml
	@# With both engines built in, the Speechmatics engine classes are unused; drop them so the count says so.
	if [ "$(VARIANT)" = deepgram ]; then rm -rf rasa-$(VARIANT)/engines rasa-$(VARIANT)/tests/test_speech_parity.py; fi

spec-rasa-variant: rasa-variant ## The 17 calls on rasa-$(VARIANT)/ (billed: model, speech-to-text, Deepgram TTS; LABEL=, BUDGET=)
	python3 shared/spec/run_spec.py rasa --server-cwd rasa-$(VARIANT) \
		--speech-prices shared/spec/speech-prices/$(PRICES_$(VARIANT)).json --label $(LABEL) --budget-usd $(BUDGET)

spec-deepgram: ## The 17 calls on FW=langgraph|strands with Deepgram speech in and out (billed; LABEL=, BUDGET=)
	python3 shared/spec/run_spec.py $(FW) \
		--server-cmd "uv run --locked python ../shared/speech-deepgram/launch.py server.py --port {port}" \
		--speech-prices shared/spec/speech-prices/deepgram.json --label $(LABEL) --budget-usd $(BUDGET)

count: ## Lines per concern for every framework folder present, and each guard diff
	@for fw in rasa langgraph strands; do \
		if [ -d $$fw ]; then python3 shared/spec/count_concerns.py $$fw; \
		test -f $$fw/guard.diff && python3 shared/spec/count_concerns.py $$fw --diff; fi; done
	@python3 shared/spec/count_concerns.py shared/speech
	@python3 shared/spec/count_concerns.py shared/speech-deepgram
	@for v in deepgram-tts deepgram; do test -d rasa-$$v && python3 shared/spec/count_concerns.py rasa-$$v; done; true
