PYTHON ?= .venv/bin/python
CONSENT_PYTHON ?= consent/.venv/bin/python
SERVER_PYTHON ?= server/.venv/bin/python

.PHONY: setup run google-signin consent setup-sheet test test-native
setup:
	python3 ../../scripts/workspace.py start . --owner shop-native
	python3 ../../scripts/workspace.py start server --owner shop-server
	python3 ../../scripts/workspace.py start consent --owner shop-consent

run:
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
