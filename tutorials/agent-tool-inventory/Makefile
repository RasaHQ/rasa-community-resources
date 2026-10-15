.PHONY: install test snapshot check
install:
	uv sync --prerelease=allow --locked

test:
	uv run --locked python -m unittest discover -s tests -v

snapshot:
	uv run --locked python inventory_cli.py snapshot . --trusted-python

check:
	uv run --locked python inventory_cli.py check . --expected inventory.json --trusted-python
