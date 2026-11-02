# Software factories workshop codespace (draft)
Open (after this is merged): https://codespaces.new/RasaHQ/rasa-community-resources?devcontainer_path=.devcontainer/software-factories-workshop/devcontainer.json
Before opening, save RASA_LICENSE and OPENAI_API_KEY as Codespaces secrets in your own GitHub settings and give this repository access. Never put a key in a file.
Status: not run. See the open questions in the sent message. The Studio start is experimental.
Studio is presenter-only. It needs RASA_STUDIO_LICENSE, a licence with a Studio entitlement. The free Developer Edition key does not unlock Studio unless Rasa hands out Studio licences.

## First win (tested in a warm 8-core codespace, Nov 1, 2026)
In a new empty folder: `"$HOME/.venv-mantle/bin/rasa" init --engine mantle --no-prompt`, then `"$HOME/.venv-mantle/bin/rasa" inspect --port 5010` and keep it running. Wait for "Rasa server is up and running". In a second terminal run `bash /workspaces/rasa-community-resources/.devcontainer/software-factories-workshop/print-inspector-url.sh` and open the address. If GitHub shows an access-port page for your own private host, choose Continue. Type Hello. The tested reply was "Hello! What can I help you with today?". The keys come from your Codespaces secrets (RASA_LICENSE, OPENAI_API_KEY). Never paste a key into a command, a file or a chat.

