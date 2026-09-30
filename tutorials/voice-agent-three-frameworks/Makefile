# The same Cedar Clinic voice agent on Rasa Mantle, LangGraph and AWS Strands Agents.
# Shared parts in shared/; one folder per framework. See README.md and COMPARISON-PLAN.md.

.DEFAULT_GOAL := help
.PHONY: help test test-clinic test-spec test-speech speech-live web count

help: ## Show targets
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  make %-12s %s\n", $$1, $$2}'

test: test-clinic test-spec test-speech ## Offline tests of the shared parts (bare python3 and uv; no network)

test-clinic: ## cedar_clinic: rules, tools, audit log
	cd shared/clinic && python3 -m unittest discover -s tests -v

test-spec: ## The spec's checks, guard invariant, LLM meter and spec file
	python3 -m unittest discover -s shared/spec/tests -v

test-speech: ## cedar_speech: Speechmatics messages, reply handling, audio (offline)
	cd shared/speech && uv run --python 3.12 python -m unittest tests.test_offline -v

speech-live: ## One live Speechmatics round trip (billed: a few seconds of realtime audio)
	cd shared/speech && uv run --python 3.12 python -m unittest tests.test_live -v

web: ## The voice page on http://127.0.0.1:8765/, relaying to the Rasa version on :5005
	python3 shared/web/serve.py rasa

count: ## Lines per concern for every framework folder present, and each guard diff
	@for fw in rasa langgraph strands; do \
		if [ -d $$fw ]; then python3 shared/spec/count_concerns.py $$fw; \
		test -f $$fw/guard.diff && python3 shared/spec/count_concerns.py $$fw --diff; fi; done
	@python3 shared/spec/count_concerns.py shared/speech
