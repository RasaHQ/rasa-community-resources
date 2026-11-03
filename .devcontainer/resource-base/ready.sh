#!/usr/bin/env bash
# Last creation step: prints one clear READY or NOT READY line for the resource. Never calls a model.
# Usage: ready.sh <resource path> [custom check command run inside the resource folder]
set -u
project="${1:?resource path}"
root="$(git rev-parse --show-toplevel)"
if [ -n "${2:-}" ]; then
  (cd "$root/$project" && bash -c "$2")
else
  python3 "$root/scripts/check_project.py" "$project" --skip-sync
fi
status=$?
# READY must mean the first command can run: every required secret has to be set (CI has none and skips this).
missing=""
if [ -z "${READY_SKIP_SECRETS:-}" ]; then
  slug="$(printf '%s' "$project" | tr / -)"
  missing="$(python3 - "$root/.devcontainer/$slug/devcontainer.json" <<'PY'
import json, os, sys
secrets = json.load(open(sys.argv[1])).get("secrets", {})
print(" ".join(name for name, item in secrets.items()
               if item.get("description", "").startswith("Required.") and not os.environ.get(name)))
PY
)"
fi
echo
if [ "$status" -eq 0 ] && [ -n "$missing" ]; then
  echo "NOT READY: $project is installed, but these required secrets are not set: $missing. Save them as personal Codespaces secrets for this repository, then stop and reopen this Codespace."
  exit 0
fi
if [ "$status" -eq 0 ]; then
  echo "READY: $project is installed, its secrets are set, and it passes its check. Start with the first command in its README."
else
  echo "NOT READY: $project did not pass its check (exit $status). Read the lines above. If you added a secret after this Codespace was created, stop and reopen it, then run the check again: $(printf '%s' "${2:-python3 scripts/check_project.py $project}")"
fi
exit 0
