.PHONY: run test validate

run:
	uv run --locked python run_demo.py --port 5005

test:
	uv run --locked python -m unittest discover -s tests -v

validate:
	uv run --locked python -c "from rasa.mantle.validation import validate_project; validate_project('.')"
