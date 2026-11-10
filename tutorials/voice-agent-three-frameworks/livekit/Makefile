# concern: ops
.PHONY: test run confirmation-countertest provider-contract
ENV_FILE := $(firstword $(wildcard .env ../../../.env))
test:
	uv run --locked python -m unittest discover -s tests -v
run:
	uv run --locked $(if $(ENV_FILE),--env-file $(ENV_FILE),) python server.py --port 5012

confirmation-countertest: ## Offline native SDK test against the prompt-only reverse patch
	uv run --locked python ../shared/spec/verify_countertest.py livekit

provider-contract: ## Check real SDK HTTP requests against a local fake provider; no spend
	uv run --locked python ../shared/spec/verify_provider_contract.py livekit

.PHONY: provider-drift
provider-drift:
	uv run --locked python ../shared/spec/verify_provider_drift.py livekit
	uv run --locked python ../shared/spec/inspect_provider.py livekit
