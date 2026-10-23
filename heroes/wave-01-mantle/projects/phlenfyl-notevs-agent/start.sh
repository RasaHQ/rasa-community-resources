#!/usr/bin/env bash
# Starts the local Rasa server. This is what the VS Code extension's
# background process manager runs — it must stay foreground (no
# backgrounding itself) so the extension can track/kill it, and it must
# `exec` into the final process so the extension's process handle IS the
# Rasa server, not a wrapper shell with an orphan child.
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -d .venv ]; then
  echo "No .venv found — run ./setup.sh first." >&2
  exit 1
fi

# GROQ_API_KEY/OPENAI_API_KEY/ANTHROPIC_API_KEY + RASA_LICENSE may already be
# set in the environment (the VS Code extension injects them from Settings →
# Agent when it spawns this script). .env is only needed when running this
# by hand — load it if present, but don't require it.
if [ -f .env ]; then
  set -a
  source .env
  set +a
fi

# Same three providers as the VS Code extension's LLM_PROVIDERS map
# (agentProcess.ts) — LLM_PROVIDER selects which one this run uses.
# set_llm_provider.py rewrites integrations.yml's llm: block to match.
LLM_PROVIDER="${LLM_PROVIDER:-groq}"
case "$LLM_PROVIDER" in
  groq) API_KEY_VAR=GROQ_API_KEY ;;
  openai) API_KEY_VAR=OPENAI_API_KEY ;;
  anthropic) API_KEY_VAR=ANTHROPIC_API_KEY ;;
  *)
    echo "Unknown LLM_PROVIDER '$LLM_PROVIDER' — must be groq, openai, or anthropic." >&2
    exit 1
    ;;
esac

if [ -z "${!API_KEY_VAR:-}" ]; then
  echo "$API_KEY_VAR is not set — add it to .env (see .env.example), matching LLM_PROVIDER=$LLM_PROVIDER." >&2
  exit 1
fi
if [ -z "${RASA_LICENSE:-}" ]; then
  echo "RASA_LICENSE is not set — add it in NoteVs Settings → Agent, or in .env if running manually." >&2
  exit 1
fi
export RASA_PRO_LICENSE="${RASA_PRO_LICENSE:-$RASA_LICENSE}"

source .venv/bin/activate

python3 set_llm_provider.py

# Confirmed live: `rasa run` serves the REST channel on :5005 reading
# integrations.yml's channels.rest, same shape as classic CALM's
# credentials.yml did — POST /webhooks/rest/webhook, {sender, message} ->
# [{text, ...}].
exec rasa run
