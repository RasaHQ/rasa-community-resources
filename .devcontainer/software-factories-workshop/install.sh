#!/usr/bin/env bash
# Credential-free preparation for a prebuild or a fresh Codespace.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
MANTLE_ENV="${WORKSHOP_MANTLE_ENV:-$HOME/.venv-mantle}"
BUILDER_ENV="${WORKSHOP_BUILDER_ENV:-$HOME/.venv-builder}"
command -v uv >/dev/null || { echo "NOT READY: uv is missing from the workshop image. Open the workshop configuration."; exit 1; }
echo "Preparing the locked Mantle environment. No keys are read."
UV_PROJECT_ENVIRONMENT="$MANTLE_ENV" uv sync --locked --python 3.12 --project "$ROOT/workshops/software-factories-masterclass/router-helper/mantle"
echo "Preparing the locked builder environment. No Agents session is started."
UV_PROJECT_ENVIRONMENT="$BUILDER_ENV" uv sync --locked --python 3.12 --project "$ROOT/workshops/software-factories-masterclass/router-helper/builder"
echo "Workshop dependencies prepared. Setup checks your own secrets after creation."
