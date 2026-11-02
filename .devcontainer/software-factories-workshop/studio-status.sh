#!/usr/bin/env bash
# Says whether Studio has finished starting in the background. Reads no key value.
LOG="$HOME/studio-start.log"
if [ ! -f "$LOG" ]; then echo "Studio has not been started. Start it with: bash /workspaces/rasa-community-resources/.devcontainer/software-factories-workshop/start-studio-background.sh"; exit 1; fi
if grep -q "STUDIO-READY" "$LOG"; then echo "Studio is ready."; grep -E "Studio:|Login" "$LOG" | tail -2; exit 0; fi
if grep -q "STUDIO-FAILED\|not started" "$LOG"; then echo "Studio did not start. Last lines of $LOG:"; tail -8 "$LOG"; exit 2; fi
echo "Studio is still starting (a cold start took about 9 minutes). Keep going with the Mantle path. Last line:"; tail -1 "$LOG"; exit 1
