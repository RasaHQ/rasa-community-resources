PYTHON := .venv/bin/python
CREW_PYTHON := ../crewai/.venv/bin/python
RASA := .venv/bin/rasa

.PHONY: install validate train run test
install:
	uv sync --prerelease=allow --locked
validate:
	$(PYTHON) -c 'from pathlib import Path; from rasa.mantle.validation import collect_project_findings; findings=collect_project_findings(Path(".")); print(findings); assert not findings'
train:
	$(RASA) train --out models
run:
	$(RASA) run --enable-api --port 5019 --interface 127.0.0.1 --model models
test:
	CREWAI_TELEMETRY_DISABLED=true OTEL_SDK_DISABLED=true $(CREW_PYTHON) -m unittest discover -s ../crewai/tests -p 'test_*.py'
	CREWAI_TELEMETRY_DISABLED=true OTEL_SDK_DISABLED=true $(PYTHON) -m unittest discover -s ../crewai-transport/tests -p 'test_*.py'
	CREWAI_TELEMETRY_DISABLED=true OTEL_SDK_DISABLED=true $(PYTHON) -m unittest discover -s tests -p 'test_*.py'
