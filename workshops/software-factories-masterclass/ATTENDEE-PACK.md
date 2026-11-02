# Attendee pack: build a dark software factory with Rasa Mantle, Rasa Studio, and the OpenAI Agents API

sow: public

Follow this page in order. Copy commands exactly. Never paste a key into a command, a file, or a chat. If a step does not match what you see, write down the words on the screen (not the keys) and ask for help early.

## Minute 0: set up and open your codespace

Nothing is set up in advance. Do this at minute 0, while the presenter shows the finished helper. It has not been timed with a first-time attendee, so the presenter will tell you the time it takes.

1. Use a personal GitHub account that is not managed by an enterprise.
2. Have these three values ready, from your own accounts and from Rasa: a free Rasa Developer Edition key (from Rasa's Developer Edition page; the confirmation page is not the key), your OpenAI API key (for the builder part it needs the permissions `api.agents.read`, `api.agents.write`, and `api.responses.write`), and the Studio licence Rasa gives you at the session. Do not share them.
3. Open the workshop repository on GitHub. Choose **Code**, then **Codespaces**, then the three dots, then **New with options**. Set **Dev container configuration** to `software-factories-workshop`, choose at least 4 cores, and set the branch the presenter names.
4. The creation page asks for three secrets, named `RASA_LICENSE` (your Developer key), `OPENAI_API_KEY` and `RASA_STUDIO_LICENSE` (the Studio licence). Paste each value into its own box. They are saved to your GitHub account for this repository. If you create the codespace without that page, add them afterwards under **Settings**, then **Codespaces**, then **New secret**, set **Repository access** to the exact repository you opened, and then stop and start the codespace.
5. Choose **Create codespace**. Studio starts by itself in the background as soon as the codespace is up.
6. Wait. The codespace can show as available while the install is still running. In the terminal, wait for the line that starts `Setup finished`. If you see `NOT READY`, read the sentence after it. It tells you which secret to fix. Fix it, then stop and start the codespace.

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

Studio starts by itself, in the background, as soon as your codespace is created. A cold start took about 9 minutes, so do the Mantle path first and come back. Check on it any time:

```bash
bash /workspaces/rasa-community-resources/.devcontainer/software-factories-workshop/studio-status.sh
```

When it says `Studio is ready.`, it prints two addresses. If it says Studio did not start, it shows the last lines of the log (`~/studio-start.log`); tell the presenter. Then follow `workshops/software-factories-masterclass/router-helper/studio/STEPS.md` in the repository. If you need to start Studio yourself, run this in a codespace terminal:

```bash
bash /workspaces/rasa-community-resources/.devcontainer/software-factories-workshop/start-studio.sh
```

It prints two addresses when it is ready. Open the login address (port 8081) first and choose **Continue** if GitHub asks, then open the Studio address (port 8080) and sign in. The presenter gives you the sign-in details. Build the two flows in STEPS.md, train, and run the four checks in the table above. The target is both paths working by minute 30. In a cold test the Studio authoring was the slow part, so work steadily and tell the presenter early if you are behind.

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
