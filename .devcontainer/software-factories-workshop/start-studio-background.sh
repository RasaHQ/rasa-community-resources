#!/usr/bin/env bash
# Starts Studio in the background when the codespace starts, so it boots while the Mantle path runs.
# Reads no key value. Logs the CURRENT attempt to ~/studio-start.log (the previous one is kept as .prev).
# Safe to run more than once: it does nothing if Studio is healthy right now or a start is already running.
# No old log line is ever a reason to skip.
set -u
LOG="$HOME/studio-start.log"
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$DIR/../.." && pwd)"
[ -f "$LOG" ] && mv -f "$LOG" "$LOG.prev"
if [ -z "${RASA_STUDIO_LICENSE:-}" ]; then
  echo "$(date -u +%T) Studio not started: RASA_STUDIO_LICENSE is not set. Add it as a Codespaces secret for this repository, then stop and start the codespace." > "$LOG"
  exit 0
fi
if bash "$DIR/studio-ready.sh"; then echo "$(date -u +%T) Studio was already healthy; nothing to start." > "$LOG"; exit 0; fi
if pgrep -f "[s]tart-studio.sh" >/dev/null 2>&1; then echo "$(date -u +%T) a start is already running" > "$LOG"; exit 0; fi
nohup setsid bash -c '
  for i in $(seq 1 60); do docker info >/dev/null 2>&1 && break; sleep 2; done
  echo "$(date -u +%T) starting Studio"
  if bash "'"$ROOT"'/.devcontainer/software-factories-workshop/start-studio.sh"; then echo "$(date -u +%T) START-FINISHED"; else echo "$(date -u +%T) STUDIO-FAILED: read the lines above"; fi
' > "$LOG" 2>&1 < /dev/null &
exit 0
