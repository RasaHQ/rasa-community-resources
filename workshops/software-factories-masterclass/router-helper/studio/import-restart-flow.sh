#!/usr/bin/env bash
# Stages the ready-made restart flow as a project and uploads it to your Studio. Reads no key value.
# The flow, domain, config and endpoints files are the ones Studio itself exported (see restart-project/PINS.txt).
# The settings below were proven once by a tester (CLI-VALUES.txt). Not yet run by an attendee.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RASA="$HOME/.venv-mantle/bin/rasa"
NAME="${1:-restart-router-helper}"
PROJECT="$HOME/restart-router-project"
bash "$HERE/../../../../.devcontainer/software-factories-workshop/studio-status.sh" || { echo "NOT READY: Studio is not ready yet. Do the Mantle path and run this again."; exit 1; }
[ -e "$PROJECT" ] && { echo "NOT READY: $PROJECT already exists. Remove it, then run this again."; exit 1; }
cp -R "$HERE/restart-project" "$PROJECT"
cd "$PROJECT"
echo
echo "Step 1 of 3: tell the Rasa CLI where Studio is. It asks four questions. Type exactly:"
echo "  Studio URL:   http://localhost:4000"
echo "  Keycloak URL: http://localhost:8081/auth/"
echo "  Realm:        press Enter"
echo "  Client ID:    press Enter"
"$RASA" studio config --advanced
echo
echo "Step 2 of 3: sign in. Username: superuser. The password is in Rasa's Studio compose README under 'Keycloak Default Users Password'."
"$RASA" studio login
echo
echo "Step 3 of 3: upload the restart flow as a new assistant named '$NAME'."
"$RASA" studio upload "$NAME"
echo
echo "Done. Open Studio, open the assistant '$NAME', change the confirmation wording, train, and try it."
