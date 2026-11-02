#!/usr/bin/env bash
# Starts Studio in the background when the codespace starts, so it boots while the Mantle path runs.
# Reads no key value. Logs to ~/studio-start.log. Safe to run more than once: it does nothing if a start is running or finished.
set -u
LOG="$HOME/studio-start.log"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
if [ -z "${RASA_STUDIO_LICENSE:-}" ]; then
  echo "$(date -u +%T) Studio not started: RASA_STUDIO_LICENSE is not set. Add it as a Codespaces secret for this repository, then stop and start the codespace." >> "$LOG"
  exit 0
fi
if pgrep -f "[s]tart-studio.sh" >/dev/null 2>&1; then exit 0; fi
if grep -q "STUDIO-READY" "$LOG" 2>/dev/null; then exit 0; fi
nohup setsid bash -c '
  for i in $(seq 1 60); do docker info >/dev/null 2>&1 && break; sleep 2; done
  echo "$(date -u +%T) starting Studio"
  if bash "'"$ROOT"'/.devcontainer/software-factories-workshop/start-studio.sh"; then echo "$(date -u +%T) STUDIO-READY"; else echo "$(date -u +%T) STUDIO-FAILED: read the lines above"; fi
' >> "$LOG" 2>&1 < /dev/null &
exit 0
