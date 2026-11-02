#!/usr/bin/env bash
# Two-minute check for a codespace you prepared the day before. Reads no key value and starts nothing that costs money.
# It prints OK or NOT READY for each thing the session needs, then tells you the one fix for any that is not.
set -u
ok() { echo "OK        $1"; }
bad() { echo "NOT READY $1 -> $2"; fail=1; }
fail=0
[ -x "$HOME/.venv-mantle/bin/rasa" ] && ok "Mantle is installed" || bad "Mantle is not installed" "run: bash /workspaces/rasa-community-resources/.devcontainer/software-factories-workshop/install.sh"
for name in RASA_LICENSE OPENAI_API_KEY RASA_STUDIO_LICENSE; do
  [ -n "${!name:-}" ] && ok "secret $name is set" || bad "secret $name is not set" "add it in GitHub Settings, Codespaces, then stop and start this codespace"
done
agent="$HOME/router-helper-agent"
[ -d "$agent/skills/router_restart" ] && ok "your router helper agent is in $agent" || bad "no router helper agent in $agent" "do the Mantle steps in the attendee pack"
ls "$agent"/models/*.tar.gz >/dev/null 2>&1 && ok "the agent is trained" || bad "the agent is not trained" "run rasa train in $agent"
docker info >/dev/null 2>&1 && ok "Docker is running (Studio needs it)" || bad "Docker is not running" "wait a minute, then run this check again"
[ -d "$HOME/studio-docker-compose" ] && ok "the Studio files are downloaded" || bad "the Studio files are not downloaded" "run start-studio.sh once"
echo
[ $fail = 0 ] && echo "All ready. Open the Inspector with: cd $agent && ~/.venv-mantle/bin/rasa inspect --port 5010" || echo "Fix the lines marked NOT READY, then run this check again."
exit $fail
