#!/usr/bin/env bash
# Installs one resource from its own lock. Usage: install.sh <resource path>
# Never installs the whole catalog and never calls a model.
set -eu
project="${1:?resource path}"
root="$(git rev-parse --show-toplevel)"
uv sync --locked --python 3.12 --project "$root/$project"
# Secrets arrive as environment variables; give the resource the .env file its Makefile expects.
bash "$root/.devcontainer/resource-base/make-env.sh" "$root/$project"
echo "Ready: $project. Check it with: python3 scripts/check_project.py $project"
