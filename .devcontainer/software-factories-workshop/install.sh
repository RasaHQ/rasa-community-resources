#!/usr/bin/env bash
# Credential-free install. It runs when the codespace is built, so a prebuild can keep it, and it reads no key.
# Installs Mantle from this repo's own pin (RASA_PRO_VERSION) in its own virtual environment.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PIN="$(tr -d '[:space:]' < "$ROOT/RASA_PRO_VERSION")"
echo "Installing rasa-pro==$PIN"
python -m venv "$HOME/.venv-mantle"
"$HOME/.venv-mantle/bin/pip" install --quiet "rasa-pro==$PIN"
echo "Mantle install finished."
