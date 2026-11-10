.PHONY: test validate train run
test:
	.venv/bin/python -B -m unittest discover -s tests -p 'test_*.py' -v
validate:
	.venv/bin/python -c 'from pathlib import Path; from rasa.mantle.validation import collect_project_findings; findings=collect_project_findings(Path(".")); print(findings); assert not findings'
train:
	.venv/bin/rasa train --fixed-model-name juniper-existing-pipecat
run:
	.venv/bin/rasa run --enable-api --port 5020 --interface 127.0.0.1 --model models
