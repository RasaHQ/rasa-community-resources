#!/usr/bin/env bash
# Installs one resource from its own lock. Usage: install.sh <resource path> [license-alias]
# Never installs the whole catalog and never calls a model.
set -eu
project="${1:?resource path}"
root="$(git rev-parse --show-toplevel)"
uv sync --locked --python 3.12 --project "$root/$project"
if [ "${2:-}" = "alias-license" ]; then
  line='export RASA_PRO_LICENSE="${RASA_PRO_LICENSE:-${RASA_LICENSE:-}}"'
  grep -qxF "$line" "$HOME/.bashrc" 2>/dev/null || echo "$line" >> "$HOME/.bashrc"
fi
echo "Ready: $project. Check it with: python3 scripts/check_project.py $project"
