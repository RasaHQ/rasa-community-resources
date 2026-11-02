#!/usr/bin/env bash
# Runs after the codespace is created, when your own secrets are available. It installs nothing.
# It checks that the install is there and that the licence in RASA_LICENSE was not rejected.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
if [ ! -x "$HOME/.venv-mantle/bin/rasa" ]; then
  echo "Installing Mantle (it was not found, so no prebuild was used)"
  bash "$ROOT/.devcontainer/software-factories-workshop/install.sh"
fi
# Installed is not the same as licensed. A licence can be present but rejected as not a JWT while a script still says ready. Capture the output without echoing any key value and say which state we are in.
version_output="$("$HOME/.venv-mantle/bin/rasa" --version 2>&1 || true)"
echo "$version_output" | grep -v -i 'eyJ' | head -20
if [ -z "${RASA_LICENSE:-}" ]; then
  echo "NOT READY: RASA_LICENSE is not set. Mantle is installed but cannot be used. Save it as a Codespaces secret scoped to this repository, then restart."
elif echo "$version_output" | grep -q -i -E 'active_license\.invalid|LicenseEncodingException|could not decode license'; then
  echo "NOT READY: Mantle is installed, but the licence in RASA_LICENSE was rejected as invalid. Replace the Codespaces secret RASA_LICENSE with the full licence string, then restart. The value is never printed here."
else
  echo "Setup finished. Mantle is installed and the licence was not rejected. Activate it with: source ~/.venv-mantle/bin/activate"
fi
echo "Start Studio with: bash $ROOT/.devcontainer/software-factories-workshop/start-studio.sh"
