.PHONY: install validate train run test
install:
	uv sync --prerelease=allow --locked --python 3.12
validate:
	uv run --locked python -c "from pathlib import Path; from rasa.mantle.validation import validate_project; validate_project(Path('.'))"
train:
	uv run --locked rasa train
run:
	uv run --locked rasa run --enable-api --port 5005
test:
	python3 -B -m unittest discover -s ../tests -v
