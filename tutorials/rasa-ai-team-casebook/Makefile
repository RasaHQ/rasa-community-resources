.PHONY: proof install validate train chat
proof:
	python3 -m unittest discover -s tests -v
install:
	uv sync
validate:
	uv run python -c "from pathlib import Path; from rasa.mantle.validation import validate_project; validate_project(Path('.'))"
train:
	uv run rasa train
chat:
	uv run rasa inspect
