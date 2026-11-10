#!/usr/bin/env bash
# Prints the private address of the Mantle Inspector in this Codespace. Run it in a second terminal while
# `make inspect` is running in the first. Usage: print-inspector-url.sh [port, default 5005]. Prints no secret.
set -euo pipefail
PORT="${1:-5005}" python3 - <<'PY'
import os, urllib.parse
port = os.environ["PORT"]
base = "https://" + os.environ["CODESPACE_NAME"] + "-" + port + "." + os.environ.get("GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN", "app.github.dev")
print(base + "/webhooks/inspector/inspect.html?" + urllib.parse.urlencode({"projectUrl": base, "channel": "inspector"}))
PY
