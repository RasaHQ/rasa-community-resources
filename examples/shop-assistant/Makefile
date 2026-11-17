.DEFAULT_GOAL := help
PYTHON ?= .venv/bin/python
CONSENT_PYTHON ?= consent/.venv/bin/python
SERVER_PYTHON ?= server/.venv/bin/python

.PHONY: help setup doctor chat-id run google-signin consent setup-sheet test test-native test-startup
help:
	@echo "setup          Create missing locked environments; reuse matching existing ones"
	@echo "doctor         Check settings by name and explain missing values"
	@echo "chat-id        Read your private chat ID after you message your own bot"
	@echo "google-signin  Authorize this Codespace to use Google Sheets"
	@echo "consent        Alias for google-signin"
	@echo "setup-sheet    Create missing tabs and seed empty tabs in your dedicated Sheet"
	@echo "run            Check settings, then start the assistant; Ctrl-C stops it"
	@echo "test           Run offline checks with fake services"
	@echo "test-startup   Run offline startup and setup checks"
	@echo "test-native    Run locked native Rasa and MCP checks with fake services"
setup:
	python3 -B setup_environments.py

doctor:
	@test -x $(CONSENT_PYTHON) || { echo "Run make setup first to create the locked environments."; exit 1; }
	$(CONSENT_PYTHON) -B -m shop_demo.startup doctor

chat-id:
	@test -x $(CONSENT_PYTHON) || { echo "Run make setup first to create the locked environments."; exit 1; }
	$(CONSENT_PYTHON) -B -m shop_demo.startup chat-id

run: doctor
	$(PYTHON) -B -m shop_demo.launcher

google-signin:
	$(CONSENT_PYTHON) -B -m shop_demo.google_signin

consent: google-signin

setup-sheet:
	$(SERVER_PYTHON) -B -m shop_demo.setup_sheet

test:
	$(CONSENT_PYTHON) -B -m unittest discover -s tests -v

test-native:
	RASA_TELEMETRY_ENABLED=false LITELLM_LOCAL_MODEL_COST_MAP=True SHOP_TEST_SERVER_PYTHON=$(abspath $(SERVER_PYTHON)) PYTHONPATH=.:tests $(PYTHON) -B tests/native_check.py -v
	PYTHONPATH=. $(SERVER_PYTHON) -B tests/integration_server_check.py -v

test-startup:
	$(CONSENT_PYTHON) -B -m unittest discover -s tests -p test_startup.py -v
