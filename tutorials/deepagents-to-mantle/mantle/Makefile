.PHONY: install validate train run test
OWNER ?= chinook-mantle-demo
install:
	python3 ../../../scripts/workspace.py start . --owner $(OWNER)
validate:
	uv run --locked python -c "from pathlib import Path; from rasa.mantle.validation import validate_project; validate_project(Path('.'))"
train:
	uv run --locked rasa train
run:
	uv run --locked rasa run --enable-api --port 5005
test:
	uv run --locked python -B -m unittest discover -s ../tests -v
