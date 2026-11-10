# Your router helper and software factory

Start in the GitHub Codespace opened from the [workshop README](README.md).
Complete its minute-zero secret and readiness steps first. Every command below
runs in that Codespace, not on your laptop. uv and the two locked environments
are already prepared. Nobody needs advance setup.

A **skill** groups instructions and tools for a task. A **tool** is a function
the helper can call. Here the tool records a simulated command; it controls no
router. A **proposal** is a separate saved Python file. The **gate** reads that
file and checks a small, fixed contract before a person records a decision.

## Your router helper: minutes 10–30

In the Codespace terminal, run these one at a time:

```bash
WORKSHOP="$(git rev-parse --show-toplevel)/workshops/software-factories-masterclass"
mkdir "$HOME/router-helper-agent"
cd "$HOME/router-helper-agent"
"$HOME/.venv-mantle/bin/rasa" init --engine mantle --no-prompt
"$HOME/.venv-mantle/bin/python" "$WORKSHOP/router-helper/mantle/install_helper.py" .
"$HOME/.venv-mantle/bin/rasa" train
"$HOME/.venv-mantle/bin/rasa" inspect --port 5010
```

The installer replaces the starter's active banking skills with this router
helper and sets its router-only instructions. If the folder already exists,
do not initialize it again: resume your last completed step with the presenter.
Keep this terminal running. Wait for `Rasa server is up and running`.

Open a second terminal, which starts in the workshop repository, and run:

```bash
bash "$(git rev-parse --show-toplevel)/.devcontainer/software-factories-workshop/print-inspector-url.sh"
```

Open the address it prints. If GitHub asks whether to continue to your own
private forwarded port, choose **Continue**. Type these in the Inspector:

| You type | Meaning to look for |
| --- | --- |
| `Restart my router` | It asks for confirmation and explains the interruption while keeping Wi-Fi settings |
| `Yes` | It reports a simulated `REBOOT` |
| `Reset it` | It asks which operation you mean, without recording a command |
| `Factory reset` | It refuses that operation and offers a person, without reset instructions |

The exact words can vary. The target is all four meanings by minute 30. If you
are not ready by minute 25, raise your hand. Record a mismatched reply and ask
for help instead of treating it as a pass. Today's assisted test runs reached
these checks at about 11 minutes after opening, using an existing account; the
complete refreshed path has not yet had an unaided cold run.

## Try a changed mind: minutes 30–50

Ask for a restart, then say `No` at confirmation. Try ambiguous wording and a
factory-reset request in another order. What was recorded? Did a new request
change the meaning of an earlier confirmation? Show the presenter any command
you did not ask for. These are your observed checks, not a promised transcript.

Explain to a partner who controls the confirmation, where `REBOOT` is stored,
and which part of the result is a simulation.

## Catch and restore a source change: minutes 50–70

Stop the Inspector with Ctrl+C in its server terminal before this exercise.
The source check reads a configured value. It is separate from the conversation
checks; a passing source check alone is not a chat result.

In the terminal that was running the helper:

```bash
SOURCE="$HOME/router-helper-agent/skills/router_restart/tools.py"
cp "$SOURCE" "$SOURCE.before-check"
"$HOME/.venv-mantle/bin/python" "$WORKSHOP/router-helper/check_helper.py" "$SOURCE"
```

Expect `PASS: a restart records REBOOT`. In the editor, change the command's
`"REBOOT"` value in `tools.py` to `"FACTORY_RESET"`. Run the same check again:

```bash
"$HOME/.venv-mantle/bin/python" "$WORKSHOP/router-helper/check_helper.py" "$SOURCE"
```

Expect `FAIL`. Now restore the file and check it before continuing:

```bash
cp "$SOURCE.before-check" "$SOURCE"
"$HOME/.venv-mantle/bin/python" "$WORKSHOP/router-helper/check_helper.py" "$SOURCE"
```

Require the restored `PASS` before retraining or restarting the Inspector. The
backup preserves any earlier edits you made; do not replace the whole project
to undo this one deliberate change.

## Connect the practice builder: minutes 75–115

The default practice mode copies the public good example into a new output
folder. It starts no Agents session and generates no new code. It lets you
check the tool connection, saved-file receipt, and gate. Mantle conversations
still use your OpenAI model account.

Open a new terminal in the repository and run:

```bash
WORKSHOP="$(git rev-parse --show-toplevel)/workshops/software-factories-masterclass"
"$HOME/.venv-builder/bin/python" "$WORKSHOP/router-helper/builder/builder_server.py" --fixture
```

Keep that terminal running. The tool endpoint is `http://127.0.0.1:8765/mcp`
inside the Codespace; its root URL is not a browser page.

In another new terminal, install the builder skill, then train and restart the
helper. The earlier Inspector must be stopped; leave the builder server running.

```bash
WORKSHOP="$(git rev-parse --show-toplevel)/workshops/software-factories-masterclass"
"$HOME/.venv-mantle/bin/python" "$WORKSHOP/router-helper/builder/change_builder/install_change_builder.py" "$HOME/router-helper-agent"
cd "$HOME/router-helper-agent"
"$HOME/.venv-mantle/bin/rasa" train
"$HOME/.venv-mantle/bin/rasa" inspect --port 5010
```

Open the Inspector using the URL-printing command from the earlier step. Ask:
`add a check that tells me the line status`. Look for a **Fixture build** label,
a build identifier, `saved a file`, an absolute path ending in
`check_line_status.py`, and a SHA-256. It should also say nothing was applied
to the helper. Keep that exact path and hash. The sample function returns fixed
teaching values; it does not probe an internet line.

If it says it cannot tell whether a build started, inspect the builder server
terminal before asking again. Missing output is not permission to start another
build. If another build is running, wait for its actual completion.

### Optional: one billed OpenAI Agents API build

Choose this only if you want to generate a proposal using your own account.
Read `INSTRUCTIONS` and `TASK` in `router-helper/builder/builder.py` first: this
builder is restricted to one fixed function, not arbitrary application changes.
Your key needs Agents API session read/write and model inference access
(`api.agents.read`, `api.agents.write`, and `api.responses.write`).

Stop the practice builder server with Ctrl+C, then restart it without the
practice flag:

```bash
"$HOME/.venv-builder/bin/python" "$WORKSHOP/router-helper/builder/builder_server.py"
```

Ask for the change **once** in the existing Inspector. This can take minutes
and is billed by OpenAI; costs were not measured for your run. Require the
actual saved path and hash, not just session completion. If the outcome is
unknown, inspect the server and retained output before retrying. Keep practice
and generated proposals labeled separately. No new paid build is needed to
finish the default practice route.

## Check the exact proposal: minutes 115–140

In a repository terminal, define `WORKSHOP` as above. Set `PROPOSAL` and
`SAVED_SHA` to the exact path and hash printed by **your** build, replacing the
quoted placeholders below:

```bash
PROPOSAL="YOUR_ABSOLUTE_SAVED_PATH"
SAVED_SHA="YOUR_64_CHARACTER_SHA256"
printf '%s  %s\n' "$SAVED_SHA" "$PROPOSAL" | sha256sum --check
"$HOME/.venv-mantle/bin/python" "$WORKSHOP/router-helper/gate/gate.py" "$PROPOSAL"
```

The first check must report `OK`. If the bytes differ, stop: the receipt names
another file version. The gate must separately report `ACCEPT`. It parses the
candidate rather than executing it. A hash match identifies bytes; gate
acceptance checks the finite function contract. Keep the reviewed file unchanged
and recheck its hash before any later use; these separate shell commands are
not an atomic release operation.

Run the fixed controls too. The deliberate REJECT results are expected:

```bash
for candidate in "$WORKSHOP"/router-helper/gate/candidates/*.py; do
  "$HOME/.venv-mantle/bin/python" "$WORKSHOP/router-helper/gate/gate.py" "$candidate"
done
```

Expect `good.py` to be ACCEPT, and `bad_opens_network.py`,
`bad_sends_reset.py`, and `bad_writes_a_file.py` to be REJECT. Never run those
candidate files directly. The checks cover these supplied failure cases, not
all possible Python behavior or real router safety.

## Record your decision: minutes 140–160

Create a short review note in your own workspace. Include the proposal's exact
path and hash, its mode (practice or generated), gate result, control results,
and your approval or refusal with a reason. Nothing is installed, applied, or
deployed by writing that note. An operational release needs its own protected
artifact and deployment procedure; this exercise ends at human review.

Use the [learning checkpoints](LEARNING-CHECKPOINTS.md) to explain the result.
The [build contract](BUILD-CONTRACT.md) records what this exercise promises.
The presenter may finish with a short Studio 2 preview and a
[Rasa Community invitation](https://info.rasa.com/community/). Attendees have
no Studio setup task.

## Finish and stop your workspace

1. Save your proposal, its path and hash, the review note, and any failure
   outputs you want to keep. Save terminal output explicitly; the visible
   terminal window is not preserved across a stop and start. Keep keys out of
   those files.
2. If a build is still running or its outcome is unknown, use the recovery
   steps below first. Closing a terminal does not confirm that a hosted Agents
   session was canceled.
3. In each terminal where you started the Inspector or builder server, press
   **Ctrl+C** and wait for the prompt. Stop your own workshop servers only.
4. Open [Your Codespaces](https://github.com/codespaces). Beside this workshop's
   Codespace, open the **…** menu and choose **Stop codespace**. Closing the
   browser tab alone leaves it running. Stopping keeps your saved workspace;
   it does not delete it. See [GitHub's stop and start instructions](https://docs.github.com/en/codespaces/developing-in-a-codespace/stopping-and-starting-a-codespace).

## Recover without guessing

| What you see | What to do |
| --- | --- |
| `NOT READY` or missing secrets | Follow the README: exact repository access, same-Codespace stop/start, explicit setup rerun, then wait for `Setup finished` |
| Dependencies still preparing | Wait for completion; ask the presenter if preparation stopped |
| Helper folder already exists | Resume the last completed step instead of initializing over it |
| Inspector cannot connect | Check its server terminal and use the printed forwarded URL, including GitHub's Continue page |
| Deliberate source FAIL | Restore the backup and require PASS before train/chat |
| No saved file/hash, or unknown build outcome | Inspect the builder terminal and existing output; do not blindly repeat the request |
| Hash mismatch or unexpected gate result | Stop, retain the proposal and outputs, and ask for review |
