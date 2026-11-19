.DEFAULT_GOAL := help
.PHONY: help run text test download doctor
help:
	@echo "Select this project with the workspace helper. Download the pinned public Jack Henry archive in examples/jack-henry-silverlake first. run uses Deepgram Nova 3 and Aura 2; text is a developer check, not voice acceptance."
run: download
	LITELLM_LOCAL_MODEL_COST_MAP=True RASA_TELEMETRY_ENABLED=false uv run --locked python doctor_profile.py
	LITELLM_LOCAL_MODEL_COST_MAP=True RASA_TELEMETRY_ENABLED=false uv run --locked python run_demo.py --port 5005
text: download
	LITELLM_LOCAL_MODEL_COST_MAP=True RASA_TELEMETRY_ENABLED=false uv run --locked python doctor_profile.py
	LITELLM_LOCAL_MODEL_COST_MAP=True RASA_TELEMETRY_ENABLED=false uv run --locked python run_demo.py --port 5005 --text-api
test:
	LITELLM_LOCAL_MODEL_COST_MAP=True RASA_TELEMETRY_ENABLED=false uv run --locked python -B -m unittest discover -s tests -v

# Reuse only the existing bank's public-download task; do not install its env.
download:
	$(MAKE) -C ../../../examples/jack-henry-silverlake download

doctor:
	LITELLM_LOCAL_MODEL_COST_MAP=True RASA_TELEMETRY_ENABLED=false uv run --locked python doctor_profile.py
