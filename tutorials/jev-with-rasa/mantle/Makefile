PYTHON := .venv/bin/python
RASA := .venv/bin/rasa

.PHONY: install test demo demo-local demo-confirmation score-demo worker worker-live worker-local validate train run
install:
	uv sync --prerelease=allow --locked
test:
	$(PYTHON) -B -m unittest discover -s ../tests -v
demo:
	$(PYTHON) -B -m jacaranda_jev.demo
score-demo:
	$(PYTHON) -B -m jacaranda_jev.score_controls
demo-confirmation:
	$(PYTHON) -B demo_confirmation.py
demo-local:
	$(PYTHON) -B -m jacaranda_jev.demo_local
worker:
	$(PYTHON) -B -m jacaranda_jev.server
worker-live:
	$(PYTHON) -B -m jacaranda_jev.server --live
worker-local:
	$(PYTHON) -B -m jacaranda_jev.server --local-laya
validate:
	$(PYTHON) -c 'from pathlib import Path; from rasa.mantle.validation import collect_project_findings; findings=collect_project_findings(Path(".")); print(findings); assert not findings'
train:
	$(RASA) train --out models
run:
	$(RASA) run --enable-api --port 5030 --interface 127.0.0.1 --model models
