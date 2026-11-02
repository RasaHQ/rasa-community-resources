# Software factories workshop codespace (draft)
Open (after this is merged): https://codespaces.new/RasaHQ/rasa-community-resources?devcontainer_path=.devcontainer/software-factories-workshop/devcontainer.json
Until then you can open the branch the presenter names.

## Secrets (do this before you open a codespace)
In your own GitHub account: **Settings**, **Codespaces**, **New secret**. Type the exact name, paste the value, under **Repository access** select the repository you will open, then **Add secret**. Add two: `RASA_LICENSE` (your free Developer Edition key) and `OPENAI_API_KEY`. A secret you add later reaches a new codespace, and a codespace that is already running only after you stop and start it. Secrets are available after the codespace is created, not in the image build. Never paste a key into a file, a command or a chat. Source: GitHub's page on account-specific secrets for Codespaces.

## First win (the router helper)
Follow `workshops/software-factories-masterclass/ATTENDEE-PACK.md`. Mantle path in short: `rasa init --engine mantle --no-prompt` in a new folder, run `router-helper/mantle/install_helper.py` on it, `rasa train`, then `rasa inspect --port 5010`. In a second terminal run `bash /workspaces/rasa-community-resources/.devcontainer/software-factories-workshop/print-inspector-url.sh` and open the address.

Status: setup and the Mantle first reply were seen working in test codespaces. The router helper's train and chat were run by testers with automated browsers. No unaided attendee has done it yet.
