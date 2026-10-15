.PHONY: test validate train run policy-review
test:
	.venv/bin/python -B -m unittest discover -s ../agno/tests -p 'test_*.py' -v
	.venv/bin/python -B -m unittest discover -s tests -p 'test_*.py' -v
	.venv/bin/python -B tests/demo_refund_identity.py
validate:
	.venv/bin/python -c 'from pathlib import Path; from rasa.mantle.validation import collect_project_findings; findings=collect_project_findings(Path(".")); print(findings); assert not findings'
train:
	.venv/bin/rasa train --fixed-model-name willowshop-existing-adviser
run:
	.venv/bin/rasa run --enable-api --port 5020 --interface 127.0.0.1 --model models

policy-review:
	PYTHONPATH=../agno python3 -B review_return_policy.py
