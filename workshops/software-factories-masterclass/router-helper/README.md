# Router restart helper

The code for the workshop's one small agent. A customer says "restart my router". The helper asks them to confirm, then records one command, `REBOOT`. It never records `FACTORY_RESET`. If the customer asks for a factory reset, it says it cannot do that here and offers a person. The command is simulated: no router is contacted.

Everything here runs in the workshop GitHub Codespace. The image has already prepared two locked environments, `~/.venv-mantle` (Rasa Mantle) and `~/.venv-builder` (the builder), so there is nothing to install. Follow [`ATTENDEE-PACK.md`](../ATTENDEE-PACK.md) for the exact commands. This page says what is in each folder.

You can tell it works when:

1. "Restart my router" makes it ask you to confirm.
2. "Yes" makes it record `REBOOT`.
3. "Reset it" makes it ask which one you mean, and it sends nothing until you answer.
4. A factory reset request gets a refusal and an offer of a person, and nothing is recorded.

## Start here: from a browser tab to your first check

Nothing needs to be installed on your laptop. You need a browser, your own GitHub
account, a free Rasa Developer Edition key and an OpenAI API key. Do A to D once,
in order.

> [!TIP]
> **Your first conversation.** Ask **Restart my router**, wait for the
> confirmation question, then answer **Yes**. In the Inspector, look for
> `command_sent: REBOOT` in the tool result.

**A. Sign in to GitHub.** A Codespace is a computer that GitHub runs for you; its
editor and terminal open in your browser. Use a personal account with Codespaces
available and enough allowance for a four-core machine.

**B. Collect two values.**

| Name to enter in GitHub | Where to get the value |
| --- | --- |
| `RASA_LICENSE` | [Request a Rasa Developer Edition license](https://rasa.com/rasa-pro-developer-edition-license-key-request). The confirmation page is not the key; copy the full license string you receive. |
| `OPENAI_API_KEY` | [Create a key in your OpenAI project](https://platform.openai.com/api-keys) with API billing and model access, and copy it while it is visible. A ChatGPT subscription is billed separately. |

**C. Save both as personal Codespaces secrets.** Open [GitHub → Settings →
Codespaces](https://github.com/settings/codespaces), choose **New secret** for
each name, paste its value, and under **Repository access** select
**RasaHQ/rasa-community-resources**. If a name already exists, edit its access
and keep any other repository you use. Never paste a key into a command, a file
or chat.

**D. Open the workshop.** [Open the workshop in GitHub
Codespaces](https://codespaces.new/RasaHQ/rasa-community-resources?ref=main&devcontainer_path=.devcontainer/software-factories-workshop/devcontainer.json).
On the creation form, check the repository, the configuration **New York
workshop: Rasa Mantle** and **at least 4 cores**, then choose **Create
codespace**. To return later, open it from [Your
codespaces](https://github.com/codespaces).

When the terminal prints a line beginning `Setup finished`, choose **Terminal →
New Terminal** and run the source-file check on the completed example. It spends
no model call:

```bash
ROUTER="$(git rev-parse --show-toplevel)/workshops/software-factories-masterclass/router-helper"
python3 "$ROUTER/check_helper.py" "$ROUTER/mantle/skills/router_restart/tools.py"
```

You should see **`PASS: a restart records REBOOT`**. If a secret was missing or
you added it after the Codespace started, stop and open the same Codespace again,
then rerun `setup.sh` as the [workshop README](../README.md#if-a-key-was-added-or-its-repository-access-changed)
describes. Then build your own helper with the commands in the
[attendee pack](../ATTENDEE-PACK.md#your-router-helper-minutes-1030).

## Create and train the helper

Open a terminal in the Codespace. The commands start a fresh folder. First check
whether `$HOME/router-helper-agent` already exists:

- If it is your earlier attempt and contains `agent.yml` and `integrations.yml`,
  change into it, skip `mkdir` and `rasa init`, and resume at `install_helper.py`.
  Keep an existing Inspector stopped while you retrain.
- If it is unrelated, keep it intact. Use `$HOME/router-helper-tutorial` instead,
  replacing every later `router-helper-agent` path. Do not delete a project to
  make a copied command succeed.
- If it is empty, change into it, skip `mkdir`, and start with `rasa init`.

**1. Create your agent.** This makes the folder your changes will live in.

```bash
WORKSHOP="$(git rev-parse --show-toplevel)/workshops/software-factories-masterclass"
mkdir "$HOME/router-helper-agent" && cd "$HOME/router-helper-agent" && "$HOME/.venv-mantle/bin/rasa" init --engine mantle --no-prompt
```

**2. Give it the router skill.** Run this from your agent folder.

```bash
"$HOME/.venv-mantle/bin/python" "$WORKSHOP/router-helper/mantle/install_helper.py" .
```

The installer moves the starter banking skills aside so the conversation uses the
router rules.

**3. Train it and start the Inspector.** The second command runs only if training
succeeds. Leave this terminal running.

```bash
"$HOME/.venv-mantle/bin/rasa" train && "$HOME/.venv-mantle/bin/rasa" inspect --port 5010
```

When it says `Rasa server is up and running`, choose **Terminal → New Terminal**
and run this in the second terminal:

```bash
bash "$(git rev-parse --show-toplevel)/.devcontainer/software-factories-workshop/print-inspector-url.sh"
```

Open the address it prints. If GitHub asks whether to continue to your own
private forwarded port, choose **Continue**. Do not make the port public to work
around a sign-in problem.

## Ask, then confirm

In the Inspector, type `Restart my router`. The helper should ask you to confirm
and explain that the connection will drop briefly while the Wi-Fi name and
password stay the same. Only then type `Yes`. It should say a restart was
recorded as `REBOOT`. These are expected meanings, not a transcript; the wording
can differ.

Open the conversation's **Inspect** view and find the restart tool call and its
result:

```json
{ "status": "sent", "command_sent": "REBOOT" }
```

If the reply sounds right but you cannot find a tool result, you have not yet
shown that the tool ran. Check the conversation's events instead of confirming
again. Then try `Reset it` and a factory-reset request, as the
[attendee pack](../ATTENDEE-PACK.md#your-router-helper-minutes-1030) lists.

**Next:** [test cancellation and factory-reset requests](https://rasa.community/library/tutorials/software-factory/02-reset-and-checks/),
[connect the builder](https://rasa.community/library/tutorials/software-factory/03-builder/)
and [judge the saved proposal](https://rasa.community/library/tutorials/software-factory/04-gate-release/).

## What is in this folder

| Path | What it is | Used at |
|---|---|---|
| `mantle/` | `install_helper.py` turns a fresh Mantle agent into the router helper: it checks first and changes nothing if anything is wrong, moves the starter banking skills into `starter-skills-moved/`, copies in the router skill, and sets a router-only persona and rules. The folder also holds a completed reference project, pinned by `pyproject.toml` and `uv.lock`. | Minutes 10 to 30 |
| `check_helper.py` | The source-file check. It reads the configured command in the helper's `tools.py`, passes when it is `REBOOT`, fails when it is anything else, and exits 2 when it finds no command. It does not watch a live conversation. | Minutes 50 to 70 |
| `builder/` | The tool server, the practice builder, the optional billed Agents API builder, and the `change_builder` skill that shows the result to the customer. See `builder/README.md`. | Minutes 75 to 115 |
| `gate/` | `gate.py` and four fixed candidate files in `gate/candidates/`: `good.py` is `ACCEPT`, and `bad_opens_network.py`, `bad_sends_reset.py` and `bad_writes_a_file.py` are `REJECT`. The gate reads a file and never runs it. | Minutes 115 to 140 |

The tests for each part sit next to it (`test_check_helper.py`, `mantle/test_install_helper.py`, `builder/test_builder_server.py`). They need no model key.

## The first path in the codespace

In short: make a new folder, run `rasa init --engine mantle --no-prompt`, run `mantle/install_helper.py` on it, `rasa train`, then `rasa inspect --port 5010`, all with the programs in `~/.venv-mantle/bin`. The attendee pack has the exact commands, the Inspector address step, and the four rows to compare.

The helper has run in a fresh test codespace, with help and an existing account. An unaided attendee has not yet run it.

## Source-file check

Run `check_helper.py` on `skills/router_restart/tools.py` inside your helper folder (exact command in the attendee pack). Change `"REBOOT"` to `"FACTORY_RESET"` and run it again to see it fail. Change it back and see it pass before you retrain.

## Optional appendix: on your own machine

This is not part of the workshop and nobody needs it. To inspect the reference project in `mantle/` outside a codespace, install `uv`, then from `mantle/` run `uv sync --locked`, `uv run rasa train`, and `uv run python -m unittest discover -s . -v`, with your own `RASA_LICENSE` and `OPENAI_API_KEY` in the environment. Training and the archive tests are separate from a live conversation test.
