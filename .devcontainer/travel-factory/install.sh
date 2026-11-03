#!/usr/bin/env bash
set -eu
here="$(cd "$(dirname "$0")/../../workshops/software-factories-masterclass" && pwd)"
UV_PROJECT_ENVIRONMENT="$HOME/.venv-mantle" uv sync --locked --python 3.12 --project "$here/env"
UV_PROJECT_ENVIRONMENT="$HOME/.venv-builder" uv sync --locked --python 3.12 --project "$here/env/builder"
mkdir -p "$HOME/.local"
npm install --prefix "$HOME/.local" @openai/codex@0.166.0
echo 'Travel factory dependencies ready. Run bash desk doctor.'
