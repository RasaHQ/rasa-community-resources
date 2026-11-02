# Attendee pack: build a dark software factory with Rasa Mantle, Rasa Studio, and the OpenAI Agents API

sow: public

Follow this page in order. Copy commands exactly. Never paste a key into a command, a file, or a chat. If a step does not match what you see, write down the words on the screen (not the keys) and ask for help early.

## Before the session

1. Use a personal GitHub account that is not managed by an enterprise.
2. Get a free Rasa Developer Edition key from Rasa's Developer Edition page. The confirmation page is not the key. The key is sent to you after you submit. You cannot share it.
3. Get an OpenAI API key from your own OpenAI account. For the builder part it needs the permissions `api.agents.read`, `api.agents.write`, and `api.responses.write`.
4. Rasa gives you a Studio licence before the session. Keep it for step 6.
5. In your GitHub account, open **Settings**, then **Codespaces**, choose **New secret**, and add three secrets. For each one, under **Repository access**, select the exact repository you will create the codespace from (the repository the presenter names; access to a different repository, or only to the Rasa organization's, will not reach a codespace made from a fork): `RASA_LICENSE` (your Developer key), `OPENAI_API_KEY`, and `RASA_STUDIO_LICENSE` (the Studio licence). Add them before you open a codespace. If you add one afterward, stop the codespace and start it again.

## Minute 0: open your codespace

1. Open the workshop repository on GitHub, choose **Code**, then **Codespaces**, then create a codespace on the branch the presenter names. Choose at least 4 cores. Do this at minute 0, while the presenter shows the finished helper.
2. Wait. The codespace can show as available while the install is still running. In the terminal, wait for the line that starts `Setup finished`. If you see `NOT READY`, read the sentence after it. It tells you which secret to fix. Fix it, then stop and start the codespace.

## Minutes 10 to 30: the Mantle path

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

The wording can differ a little. The meaning must match. If any row does not match, write down what it said and tell the presenter.

## Minutes 10 to 30: the Studio path

Studio takes a long time to start the first time: a cold start took about 9 minutes (533 seconds) after the codespace was ready. So start Studio the day before, as in `ATTENDEE-PACK-PREWORK.md`, step 4, and stop the codespace. If you did not, start it now and do the Mantle path while it starts. Follow `workshops/software-factories-masterclass/router-helper/studio/STEPS.md` in the repository. Start Studio first in a codespace terminal:

```bash
bash /workspaces/rasa-community-resources/.devcontainer/software-factories-workshop/start-studio.sh
```

It prints two addresses when it is ready. Open the login address (port 8081) first and choose **Continue** if GitHub asks, then open the Studio address (port 8080) and sign in. The presenter gives you the sign-in details. Then build the two flows in STEPS.md, train, and run the same four checks as in the table above.

## Minutes 30 to 50: the other path

Do the path you did not do. Then answer these three questions on paper: Which path asked you to confirm, and who wrote the confirmation? Where is `REBOOT` stored on each? What files does each path keep?

## Minutes 50 to 70: the first check

```bash
python3 /workspaces/rasa-community-resources/workshops/software-factories-masterclass/router-helper/check_helper.py "$HOME/router-helper-agent/skills/router_restart/tools.py"
```

You should see `PASS: a restart records REBOOT`. Now change `"REBOOT"` to `"FACTORY_RESET"` in that `tools.py`, run the command again, and you should see `FAIL`. Change it back.

## Minutes 75 to 115: your builder, with the OpenAI Agents API

Follow `workshops/software-factories-masterclass/router-helper/builder/README.md`. In short: make a separate environment for the builder, edit the instructions in `builder.py`, run it, and watch the session's events. It prints the path and sha256 of the file it saved. Then start the tool server in a second terminal and connect it to your helper as the README shows.

## Minutes 115 to 160: the gate and the release

```bash
python3 /workspaces/rasa-community-resources/workshops/software-factories-masterclass/router-helper/gate/gate.py PATH_TO_THE_SAVED_FILE
```

Use the exact path the builder printed. Also run it on the three files in `router-helper/gate/candidates/` and compare. The gate prints `ACCEPT` or `REJECT` and the names of the tests that failed. It never runs the change it judges. Then, as the person at the last gate, decide whether to release or refuse the change, and write your decision down.

## If something fails

| What you see | What to do |
|---|---|
| The codespace will not open | Pair with a neighbor |
| `NOT READY` in setup | Fix the secret it names, then stop and start the codespace |
| The first command in a block is not found | Wait for `Setup finished`, then try again |
| The Inspector says something went wrong | Do not retry an unchanged key. Write down the words on screen, without keys, and tell the presenter |
| Studio's login page will not load | Open port 8081 first and choose Continue, then try 8080 |
