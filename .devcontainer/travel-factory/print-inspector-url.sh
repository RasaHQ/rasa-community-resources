#!/usr/bin/env bash
# Prints the private address of the Mantle Inspector page in this codespace. Run it in a second terminal while
# `rasa inspect --port 5010` is running in the first. Prints no secret. The address uses the forwarded HTTPS host for
# both the page and the projectUrl query, which is the form that worked in a tested run.
set -euo pipefail
python3 - <<'PY'
import os, urllib.parse
base = "https://" + os.environ["CODESPACE_NAME"] + "-5010." + os.environ.get("GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN", "app.github.dev")
print(base + "/webhooks/inspector/inspect.html?" + urllib.parse.urlencode({"projectUrl": base, "channel": "inspector"}))
PY
