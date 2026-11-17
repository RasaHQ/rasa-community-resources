.DEFAULT_GOAL := help
.PHONY: help setup doctor run test validate download models models-check

ARCHIVE := vendor-inputs/TPG_R2026.1.00_XSD.zip
URL     := https://jkhy.github.io/devrel-assets/cms-files/soap/TPG_R2026.1.00_XSD.zip
SHA256  := a433a01b05925bd9af2bb12184046443574eba98c4fbf65b716b73cad6ff7900

help:
	@echo "SilverLake fictional banking example"
	@echo "  make help          Show these commands (also the default for make)."
	@echo "  make setup         Install or reuse the locked Python environment."
	@echo "  make doctor        Check key names, vendor archive and installed runtime."
	@echo "  make download      Download and check the tested public vendor archive."
	@echo "  make run           Check prerequisites, then start the Inspector."
	@echo "  make test          Run the example tests."
	@echo "  make validate      Validate the Rasa configuration."
	@echo "  make models        Regenerate models from the tested vendor archive."
	@echo "  make models-check  Check generated models without changing them."

setup:
	python3 setup_environment.py

doctor:
	uv run --locked python -m silverlake_demo.startup doctor

run: doctor
	uv run --locked python run_demo.py --port 5005

test:
	uv run --locked --group models python -m unittest discover -s tests -v

validate:
	uv run --locked python -c "from rasa.mantle.validation import validate_project; validate_project('.')"

# A manual learner step: fetch Jack Henry's public schema archive and check its hash.
# Nothing else (build, tests, launch) ever downloads vendor files.
download:
	@mkdir -p vendor-inputs
	@curl -fsSL -o $(ARCHIVE).part "$(URL)"
	@echo "$(SHA256)  $(ARCHIVE).part" | sha256sum -c --quiet - && mv $(ARCHIVE).part $(ARCHIVE) && echo "Saved and checked: $(ARCHIVE)" || { rm -f $(ARCHIVE).part; echo "The download does not match the expected file. Nothing was saved."; exit 1; }

# Regenerate silverlake_demo/vendor_models/ from the pinned archive (needs it in vendor-inputs/).
models:
	uv run --locked --group models python make_models.py

models-check:
	uv run --locked --group models python make_models.py --check
