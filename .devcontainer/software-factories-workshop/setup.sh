#!/usr/bin/env bash
# Check preparation and secret availability without printing secret values.
set -euo pipefail
MANTLE_ENV="${WORKSHOP_MANTLE_ENV:-$HOME/.venv-mantle}"
if ! command -v uv >/dev/null; then
  echo "NOT READY: uv is missing. Open the software-factories-workshop Codespaces configuration."
  exit 1
fi
if [ -z "${RASA_LICENSE:-}" ]; then
  echo "NOT READY: RASA_LICENSE is missing. Save it for this exact repository, stop and start this Codespace, then rerun setup.sh."
  exit 1
fi
if [ -z "${OPENAI_API_KEY:-}" ]; then
  echo "NOT READY: OPENAI_API_KEY is missing. Save it for this exact repository, stop and start this Codespace, then rerun setup.sh."
  exit 1
fi
if [ ! -x "$MANTLE_ENV/bin/rasa" ]; then
  echo "NOT READY: the Mantle installation is incomplete. Wait for dependency preparation; ask the presenter if it stopped."
  exit 1
fi
if ! version_output="$("$MANTLE_ENV/bin/rasa" --version 2>&1)"; then
  echo "NOT READY: Mantle's version/license check failed. Ask the presenter; never paste keys into logs or chat."
  exit 1
fi
if echo "$version_output" | grep -q -i -E 'active_license\.invalid|LicenseEncodingException|could not decode license'; then
  echo "NOT READY: RASA_LICENSE was rejected. Correct the repository-scoped secret, stop and start this Codespace, then rerun setup.sh."
  exit 1
fi
echo "Setup finished. Mantle's license check completed and OPENAI_API_KEY is present. The helper conversation tests model access."
