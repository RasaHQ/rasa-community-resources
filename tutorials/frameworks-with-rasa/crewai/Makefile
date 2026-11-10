PYTHON := .venv/bin/python

.PHONY: install test
install:
	uv sync --locked
test:
	CREWAI_TELEMETRY_DISABLED=true $(PYTHON) -m unittest discover -s tests -p 'test_*.py'
