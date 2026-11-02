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
if { [ -f "$HOME/.studio-start.pid" ] && kill -0 "$(cat "$HOME/.studio-start.pid")" 2>/dev/null; } || pgrep -f "[s]tart-studio.sh" >/dev/null 2>&1; then
  [ -f "$LOG.prev" ] && mv -f "$LOG.prev" "$LOG"   # keep the running attempt's log
  echo "$(date -u +%T) a start is already running; this call did nothing" >> "$LOG"; exit 0
fi
PIDFILE="$HOME/.studio-start.pid"
echo "$(date -u +%T) postStart ran; launching the background start (user $(id -un), docker socket: $(ls /var/run/docker.sock 2>&1 | head -1))" > "$LOG"
# Launch with Python's Popen in a new session. Popen returns only after the child has started, so the lifecycle
# command cannot exit before the background start exists. (Contributed after a fresh codespace showed an empty log
# and no process when a shell background job was used.) STUDIO_START_SCRIPT can name another script, for tests.
STUDIO_START_SCRIPT="${STUDIO_START_SCRIPT:-$ROOT/.devcontainer/software-factories-workshop/start-studio.sh}" \
python3 - "$LOG" "$PIDFILE" <<'PY_LAUNCH'
import os
import subprocess
import sys

log_path, pid_path = sys.argv[1:]
script = r'''
echo "$(date -u +%T) background start running as pid $$, waiting for Docker"
for i in $(seq 1 90); do docker info >/dev/null 2>&1 && break; sleep 2; done
if docker info >/dev/null 2>&1; then echo "$(date -u +%T) Docker is up"; else echo "$(date -u +%T) Docker is NOT up after 3 minutes"; fi
echo "$(date -u +%T) starting Studio"
if bash "$STUDIO_START_SCRIPT"; then echo "$(date -u +%T) START-FINISHED"; else echo "$(date -u +%T) STUDIO-FAILED: read the lines above"; fi
'''
with open(log_path, "a") as log:
    child = subprocess.Popen(
        ["bash", "-c", script, "studio-background"],
        stdin=subprocess.DEVNULL,
        stdout=log,
        stderr=subprocess.STDOUT,
        start_new_session=True,
        env=os.environ,
    )
with open(pid_path, "w") as handle:
    handle.write(str(child.pid))
print(f"Studio startup launched (PID {child.pid}); follow {log_path}")
PY_LAUNCH
exit 0
