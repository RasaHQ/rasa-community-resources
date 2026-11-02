# Attendee pack: build a dark software factory with Rasa Mantle, Rasa Studio, and the OpenAI Agents API

sow: public

Follow this page in order. Copy commands exactly. Never paste a key into a command, a file, or a chat. If a step does not match what you see, write down the words on the screen (not the keys) and ask for help early.

This workshop simulates a router command. It does not contact a router or change your internet connection. The "command" you inspect is the result the helper would send.

## Minute 0: set up and open your codespace

Nothing is set up in advance. Do this at minute 0, while the presenter shows the finished helper. Nobody has timed this step for a first-time attendee. The presenter will track setup time and help if you get stuck.

1. Use a personal GitHub account that is not managed by an enterprise.
2. Have these three values ready, from your own accounts and from Rasa: a free Rasa Developer Edition key, your OpenAI application programming interface (API) key, and the Studio license Rasa gives you at the session. Get the Developer Edition key from Rasa's Developer Edition page. The confirmation page is not the key. For the builder part, your OpenAI key needs the permissions `api.agents.read`, `api.agents.write`, and `api.responses.write`. Do not share these values.
3. Open the workshop repository on GitHub. Choose **Code**, then **Codespaces**, then the three dots, then **New with options**. Set **Dev container configuration** to `software-factories-workshop`, choose at least 4 cores, and set the branch the presenter names.
4. The creation page asks for three secrets, named `RASA_LICENSE` (your Developer key), `OPENAI_API_KEY`, and `RASA_STUDIO_LICENSE` (the Studio license). Paste each value into its own box. They are saved to your GitHub account for this repository. If you create the codespace without that page, add them afterward under **Settings**, then **Codespaces**, then **New secret**. Set **Repository access** to the exact repository you opened, and then stop and start the codespace.
5. Choose **Create codespace**. Studio starts by itself in the background as soon as the codespace is up.
6. Wait. The codespace can show as available while the install is still running. In the terminal, wait for the line that starts `Setup finished`. If you see `NOT READY`, read the sentence after it. It tells you which secret to fix. Fix it, then stop and start the codespace.

## Minutes 10 to 30: your first path

Choose your first path. If Studio is still starting, begin with Mantle. By minute 30, the target on your chosen path is a restart helper that asks for confirmation. Try the other path between minutes 30 and 50. Nobody has yet confirmed that a first-time attendee can do this in 30 minutes.

### The Mantle path

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

The wording can differ a little. The meaning must match. If any row does not match, write down what it said and tell the presenter. The Mantle path covers all four rows by minute 30.

### The Studio path

Studio starts by itself, in the background, as soon as your codespace is created. Startup time varies. In one cold test the Studio launcher took about 9 minutes after the setup finished, which was 16 minutes after opening the codespace. If it is not ready, do the Mantle path first and come back. Check on it any time:

```bash
bash /workspaces/rasa-community-resources/.devcontainer/software-factories-workshop/studio-status.sh
```

When it says `Studio is ready.`, it prints two addresses. If it says Studio did not start, it shows the last lines of the log (`~/studio-start.log`). Tell the presenter. If you need to start Studio yourself, run this in a codespace terminal:

```bash
bash /workspaces/rasa-community-resources/.devcontainer/software-factories-workshop/start-studio.sh
```

It prints two addresses when it is ready. Open the login address (port 8081) first and choose **Continue** if GitHub asks. Then open the Studio address (port 8080) and sign in as `superuser`. The password is in Rasa's Studio compose README under "Keycloak Default Users Password".

**If Studio is your first path, the target by minute 30 is to import the ready-made restart flow, change one thing, train, and try it.** Authoring a flow by hand in Studio took too long in a cold test, so you start from the restart flow Studio itself exported. In a codespace terminal, run:

```bash
bash /workspaces/rasa-community-resources/workshops/software-factories-masterclass/router-helper/studio/import-restart-flow.sh
```

It prints the Studio questions for you to type, signs you in as `superuser`, and uploads the flow as an assistant named `restart-router-helper`. Then in Studio, open that assistant and open its `restart_router` flow. Click the confirmation question node (its label is the question text), then click **Edit response**, which opens the content management system (CMS) **Responses** page. Do not use the top **Edit** button there. It only renames the response. The confirmation wording is in the plain-text box on that page ("Type to add response"). Change it (for example, change "for a short time" to "briefly"), and check the new wording is still there after you reload the page. Choose **Train**, select **Draft** for the flow, wait for **Training successful**, open **Try your assistant**, and run the first two rows of the table above: it asks for confirmation, and it records REBOOT.

The import has been checked in pieces by a tester. Configuration, login, and upload took about 12 seconds in all. A tester has also done the whole route once on a warm, already running Studio: the import script, the wording edit, training, and a chat that showed the edited confirmation and the REBOOT reply. No attendee has done it, and it has not been timed cold.

## Minutes 30 to 50: the other path, and the Studio reset flow

If you did the Mantle path first, do the Studio import above. If you did Studio first, do the Mantle path above. On the Studio path, then build the reset flow by hand with step 6 of `workshops/software-factories-masterclass/router-helper/studio/STEPS.md` (the earlier steps are replaced by the import), and run the last two rows of the table. The target is all four rows on both paths by minute 50.

Then answer these three questions on paper: Which path asked you to confirm, and who wrote the confirmation? Where is `REBOOT` stored on each? What files does each path keep?

## Minutes 50 to 70: the source-file check

This check reads the configured restart command in a file. It does not watch a live conversation, so a pass does not prove the helper ran that command.

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
