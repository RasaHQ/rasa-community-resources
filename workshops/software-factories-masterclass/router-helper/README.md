# Router restart helper

The code for the workshop's one small agent. A customer says "restart my router". The helper asks them to confirm, then records one command, `REBOOT`. It never records `FACTORY_RESET`. If the customer asks for a factory reset, it says it cannot do that here and offers a person. The command is simulated: no router is contacted.

Everything here runs in the workshop GitHub Codespace. The image has already prepared two locked environments, `~/.venv-mantle` (Rasa Mantle) and `~/.venv-builder` (the builder), so there is nothing to install. Follow [`ATTENDEE-PACK.md`](../ATTENDEE-PACK.md) for the exact commands. This page says what is in each folder.

You can tell it works when:

1. "Restart my router" makes it ask you to confirm.
2. "Yes" makes it record `REBOOT`.
3. "Reset it" makes it ask which one you mean, and it sends nothing until you answer.
4. A factory reset request gets a refusal and an offer of a person, and nothing is recorded.

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
