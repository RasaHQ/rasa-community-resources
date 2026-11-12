.PHONY: run test validate download

ARCHIVE := vendor-inputs/TPG_R2026.1.00_XSD.zip
URL     := https://jkhy.github.io/devrel-assets/cms-files/soap/TPG_R2026.1.00_XSD.zip
SHA256  := a433a01b05925bd9af2bb12184046443574eba98c4fbf65b716b73cad6ff7900

run:
	uv run --locked python run_demo.py --port 5005

test:
	uv run --locked python -m unittest discover -s tests -v

validate:
	uv run --locked python -c "from rasa.mantle.validation import validate_project; validate_project('.')"

# A manual learner step: fetch Jack Henry's public schema archive and check its hash.
# Nothing else (build, tests, launch) ever downloads vendor files.
download:
	@mkdir -p vendor-inputs
	@curl -fsSL -o $(ARCHIVE).part "$(URL)"
	@echo "$(SHA256)  $(ARCHIVE).part" | sha256sum -c --quiet - && mv $(ARCHIVE).part $(ARCHIVE) && echo "Saved and checked: $(ARCHIVE)" || { rm -f $(ARCHIVE).part; echo "The download does not match the expected file. Nothing was saved."; exit 1; }
