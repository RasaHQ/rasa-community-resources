.PHONY: install run check-inputs contract-test validate test reset-fixture
install:
	uv sync --prerelease=allow --locked
run:
	uv run --locked python run_demo.py
check-inputs:
	uv run --locked python run_demo.py --check-inputs
contract-test:
	uv run --locked python -m unittest discover -s tests -p test_vendor_contract.py -v
validate:
	uv run --locked python -c "from pathlib import Path; from rasa.mantle.validation import validate_project; validate_project(Path.cwd())"
test:
	uv run --locked python -m unittest discover -s tests -v
reset-fixture:
	@test -n "$(REASON)" || { echo 'Supply a nonsecret REASON and stop every running copy first.'; exit 2; }
	uv run --locked python run_demo.py --reset-fixture --ack-unknown --reason "$(REASON)"
