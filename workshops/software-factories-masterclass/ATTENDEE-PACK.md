# Attendee pack: build a dark software factory with Rasa Mantle and the OpenAI Agents API

sow: public

Follow this page in order. Copy commands exactly. Never paste a key into a command, a file, or a chat. If a step does not match what you see, write down the words on the screen (not the keys) and ask for help early.

This workshop simulates a router command. It does not contact a router or change your internet connection. The "command" you inspect is the result the helper would send.

## Minute 0: set up and open your codespace

Nothing is set up in advance. Do this at minute 0, while the presenter shows the finished helper. Nobody has timed this step for a first-time attendee. The presenter will track setup time and help if you get stuck.

1. Use a personal GitHub account that is not managed by an enterprise.
2. Have these two values ready, from your own accounts: a free Rasa Developer Edition key and your OpenAI application programming interface (API) key. Get the Developer Edition key from Rasa's Developer Edition page. The confirmation page is not the key. For the builder part, your OpenAI key needs the permissions `api.agents.read`, `api.agents.write`, and `api.responses.write`. Do not share these values.
3. Open the workshop repository on GitHub. Choose **Code**, then **Codespaces**, then the three dots, then **New with options**. Set **Dev container configuration** to `software-factories-workshop`, choose at least 4 cores, and set the branch the presenter names.
4. The creation page asks for two secrets, named `RASA_LICENSE` (your Developer key) and `OPENAI_API_KEY`. Paste each value into its own box. They are saved to your GitHub account for this repository. If you create the codespace without that page, add them afterward under **Settings**, then **Codespaces**, then **New secret**. Set **Repository access** to the exact repository you opened, and then stop and start the codespace.
5. Choose **Create codespace**.
6. Wait. The codespace can show as available while the install is still running. In the terminal, wait for the line that starts `Setup finished`. If you see `NOT READY`, read the sentence after it. It tells you which secret to fix. Fix it, then stop and start the codespace.

## Minutes 10 to 30: your router helper

By minute 30, the target is a restart helper that asks for confirmation. Nobody has yet confirmed that a first-time attendee can do this in 30 minutes.

Run these in the codespace terminal, one at a time:

```bash
mkdir "$HOME/router-helper-agent"
cd "$HOME/router-helper-agent"
"$HOME/.venv-mantle/bin/rasa" init --engine mantle --no-prompt
"$HOME/.venv-mantle/bin/python" /workspaces/rasa-community-resources/workshops/software-factories-masterclass/router-helper/mantle/install_helper.py .
"$HOME/.venv-mantle/bin/rasa" train
"$HOME/.venv-mantle/bin/rasa" inspect --port 5010
```

Keep that terminal running. Wait for `Rasa server is up and running`. Open a second terminal and run:

```bash
bash /workspaces/rasa-community-resources/.devcontainer/software-factories-workshop/print-inspector-url.sh
```

Open the address it prints. If GitHub shows a page asking you to continue to your own private port, choose **Continue**. Then type each of these into the Inspector, one at a time, and compare:

| You type | You should see |
|---|---|
| `Restart my router` | It asks you to confirm, and says your internet will drop for a short time and your Wi-Fi name and password stay the same |
| `Yes` | It says a restart (REBOOT) was sent |
| `Reset it` | It asks whether you mean a restart or a factory reset, and sends nothing |
| `Factory reset` | It says it cannot do that here and offers a person. It gives no steps for a factory reset |

The wording can differ a little. The meaning must match. If any row does not match, write down what it said and tell the presenter. The target is all four rows by minute 30. A tester ran an earlier version of this path cold on an existing account, with help, in 11 minutes 52 seconds. The latest text of this page has not been followed unchanged in a full cold, unaided run.

## Minutes 30 to 50: reset handling and your own change

Work through the four rows again, in a different order, and try your own wording. Ask for a restart, then change your mind. Ask for a reset in different words. Write down what the helper did each time and whether it ever recorded anything you did not ask for.

Then answer these questions on paper: Who wrote the confirmation, you or the engine? Where is `REBOOT` stored? What files does the helper keep?

## Minutes 50 to 70: the source-file check

This check reads the configured restart command in a file. It does not watch a live conversation, so a pass does not prove the helper ran that command.

```bash
python3 /workspaces/rasa-community-resources/workshops/software-factories-masterclass/router-helper/check_helper.py "$HOME/router-helper-agent/skills/router_restart/tools.py"
```

You should see `PASS: a restart records REBOOT`. Now change `"REBOOT"` to `"FACTORY_RESET"` in that `tools.py`, run the command again, and you should see `FAIL`. Change it back.

## Minutes 75 to 115: your builder, with the OpenAI Agents API

This part is not yet proven end to end by someone following this page, so say so if it fails. In terminal 1:

```bash
B=/workspaces/rasa-community-resources/workshops/software-factories-masterclass/router-helper/builder
python3 -m venv "$HOME/.venv-builder"
"$HOME/.venv-builder/bin/pip" install --upgrade openai mcp==1.28.1
"$HOME/.venv-builder/bin/python" "$B/builder.py"
```

It runs one builder session (one paid run, a few minutes), prints the session's events, and ends with `saved: True`, the file's absolute path, and its sha256. Keep that path for the gate. Open a second terminal (each terminal needs its own `B`) and start the tool server. Leave it running:

```bash
B=/workspaces/rasa-community-resources/workshops/software-factories-masterclass/router-helper/builder
"$HOME/.venv-builder/bin/python" "$B/builder_server.py"
```

Open a third terminal. First stop the Inspector from minute 0 to 30: click its terminal and press Ctrl+C (leave the tool server running). Then install the skill into your helper (this also raises Mantle's tool wait from 10 seconds to 450, because a build takes minutes), train, and open the Inspector again:

```bash
B=/workspaces/rasa-community-resources/workshops/software-factories-masterclass/router-helper/builder
"$HOME/.venv-mantle/bin/python" "$B/change_builder/install_change_builder.py" "$HOME/router-helper-agent"
cd "$HOME/router-helper-agent"
"$HOME/.venv-mantle/bin/rasa" train
"$HOME/.venv-mantle/bin/rasa" inspect --port 5010
```

Ask the helper: `add a check that tells me the line status`. Expected: one message that begins `Build ` and gives a build id, `saved a file`, an absolute path ending in `check_line_status.py`, a sha256, and `Nothing was applied to the helper.` If it says `I cannot tell whether a build started`, look at terminal 2 before asking again. Only `No build started` means the request was refused because another build was running.

## Minutes 115 to 160: the gate and the release

```bash
python3 /workspaces/rasa-community-resources/workshops/software-factories-masterclass/router-helper/gate/gate.py PATH_TO_THE_SAVED_FILE
```

Use the exact path the builder printed. Also run it on the four files in `router-helper/gate/candidates/` (one good, three bad) and compare. Expected: `good.py` is `ACCEPT`, and the three `bad_` files are `REJECT`. The gate prints `ACCEPT` or `REJECT` and the names of the tests that failed. It never runs the change it judges. Then, as the person at the last gate, decide whether to release or refuse the change, and write your decision down.

## If something fails

| What you see | What to do |
|---|---|
| The codespace will not open | Pair with a neighbor |
| `NOT READY` in setup | Fix the secret it names, then stop and start the codespace |
| The first command in a block is not found | Wait for `Setup finished`, then try again |
| The Inspector says something went wrong | Do not retry an unchanged key. Write down the words on screen, without keys, and tell the presenter |
