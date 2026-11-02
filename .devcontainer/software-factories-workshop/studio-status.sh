#!/usr/bin/env bash
# Says whether Studio is ready NOW. Readiness comes from the containers' current health, never from an old log line.
# Reads no key value.
LOG="$HOME/studio-start.log"
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if bash "$DIR/studio-ready.sh"; then
  d="${GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN:-app.github.dev}"
  echo "Studio is ready now."
  echo "Login (open first):  https://${CODESPACE_NAME}-8081.${d}/auth/"
  echo "Studio:              https://${CODESPACE_NAME}-8080.${d}"
  exit 0
fi
if pgrep -f "[s]tart-studio.sh" >/dev/null 2>&1; then echo "Studio is still starting (a cold start took about 9 minutes). Keep going with the Mantle path. Last log line:"; tail -1 "$LOG" 2>/dev/null; exit 1; fi
if [ ! -f "$LOG" ]; then echo "Studio has not been started. Start it with: bash /workspaces/rasa-community-resources/.devcontainer/software-factories-workshop/start-studio-background.sh"; exit 1; fi
echo "Studio is not running and is not ready. Last lines of $LOG:"; tail -8 "$LOG"; exit 2
