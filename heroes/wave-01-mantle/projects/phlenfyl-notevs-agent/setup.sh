#!/usr/bin/env bash
# One-time setup: creates a venv and installs rasa-pro into it.
# Run manually once — the VS Code extension's auto-start never runs this
# itself, only start.sh, so it never silently installs anything on its own.
set -euo pipefail
cd "$(dirname "$0")"

# rasa-pro supports Python 3.10-3.13 only. Plain `python3` on a modern
# Homebrew install can resolve to something newer (e.g. 3.14) that pip
# will silently reject with "No matching distribution found" — so search
# for a compatible interpreter explicitly instead of assuming `python3` is it.
PYTHON_BIN=""
for candidate in python3.13 python3.12 python3.11 python3.10; do
  if command -v "$candidate" >/dev/null 2>&1; then
    PYTHON_BIN="$candidate"
    break
  fi
done
if [ -z "$PYTHON_BIN" ]; then
  if command -v python3 >/dev/null 2>&1; then
    ver=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    case "$ver" in
      3.10|3.11|3.12|3.13) PYTHON_BIN="python3" ;;
    esac
  fi
fi
if [ -z "$PYTHON_BIN" ]; then
  echo "No compatible Python found (need 3.10-3.13; rasa-pro doesn't support 3.14+ yet)." >&2
  echo "Install one with: brew install python@3.12" >&2
  exit 1
fi
echo "Using $PYTHON_BIN ($("$PYTHON_BIN" --version))"

if [ ! -d .venv ]; then
  echo "Creating virtualenv (.venv)..."
  "$PYTHON_BIN" -m venv .venv
fi

source .venv/bin/activate
echo "Installing rasa-pro (this can take a few minutes)..."
pip install --upgrade pip
pip install -r requirements.txt

if [ ! -f .env ]; then
  cp .env.example .env
  echo ""
  echo "Created .env — fill in GROQ_API_KEY and RASA_LICENSE before running start.sh"
else
  echo ""
  echo ".env already exists, leaving it alone"
fi

echo "Setup done. Run ./start.sh to start the agent server."
