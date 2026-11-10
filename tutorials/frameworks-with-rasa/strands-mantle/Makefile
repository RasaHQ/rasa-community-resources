PYTHON := .venv/bin/python
RASA := .venv/bin/rasa

.PHONY: install validate train run test
install:
	uv sync --prerelease=allow --locked
validate:
	$(PYTHON) -c 'from pathlib import Path; from rasa.mantle.validation import collect_project_findings; findings=collect_project_findings(Path(".")); print(findings); assert not findings'
train:
	$(RASA) train --out models
run:
	$(RASA) run --enable-api --port 5018 --interface 127.0.0.1 --model models
test:
	$(PYTHON) -m unittest discover -s ../strands/tests -p 'test_*.py'
	$(PYTHON) -m unittest discover -s tests -p 'test_*.py'
