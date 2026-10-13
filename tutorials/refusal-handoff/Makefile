.PHONY: install native-test validate
install:
	uv sync --prerelease=allow --locked --python 3.12
native-test:
	uv run --locked python -B -m unittest discover -s tests -v
validate:
	uv run --locked python -c "from pathlib import Path; from rasa.mantle.validation import validate_project; validate_project(Path('.'))"
