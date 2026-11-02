#!/usr/bin/env bash
# Stages the ready-made restart flow as a project and uploads it to your Studio. Reads no key value.
# The flow and domain files are the ones Studio itself exported (see restart-project/PINS.txt).
# NOT run yet by anyone. Open questions are listed at the end of this file.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RASA="$HOME/.venv-mantle/bin/rasa"
NAME="${1:-restart-router-helper}"
PROJECT="$HOME/$NAME"
bash "$HERE/../../../../.devcontainer/software-factories-workshop/studio-status.sh" || { echo "NOT READY: Studio is not ready yet. Do the Mantle path and run this again."; exit 1; }
[ -f "$HERE/restart-project/config.yml" ] && [ -f "$HERE/restart-project/endpoints.yml" ] || { echo "NOT READY: restart-project/config.yml or endpoints.yml is missing from the repository"; exit 1; }
[ -e "$PROJECT" ] && { echo "NOT READY: $PROJECT already exists. Use another name: bash import-restart-flow.sh another-name"; exit 1; }
cp -R "$HERE/restart-project" "$PROJECT"
cd "$PROJECT"
echo "Next, the Rasa CLI asks where Studio is. Studio is at http://localhost:8080 from inside this codespace."
"$RASA" studio config
echo "Now sign in with the Studio login the presenter gives you (the CLI asks for username and password)."
"$RASA" studio login
"$RASA" studio upload
echo "Uploaded as '$NAME'. Open Studio, open that assistant, change one thing in the confirmation message, train, and try it."
# Open questions, to be answered by a run: whether rasa studio config accepts http://localhost:8080 while Studio's login address is
# the forwarded HTTPS one; whether the Mantle environment's CLI (3.21.0.dev5) uploads to Studio 1.15.2 with model service 3.15.8;
# which login to use. The pack says what actually happened.
