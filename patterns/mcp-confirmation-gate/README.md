# Test confirmation before a Rasa tool runs

```text
Author:        Rasa community team
Assessed on:   2026-10-15
Assessed by:   Locked installation, native validation and paired runtime controls
Verified with: rasa-pro 3.21.0.dev5, Python 3.12, mcp 1.28.1  <!-- rasa-version-ignore: frozen tested release -->
Audience:      Engineers connecting MCP tools to a Rasa agent
Time:          About 30 minutes for the local exercise, excluding installation
```

Use this pattern to check what your agent does when a model requests a tool
that needs confirmation. A local MCP server supplies a fictional support case.
Scripted model responses request a separate local tool that simulates recording,
so you can compare
the same request with confirmation enabled and disabled.

The engine, MCP transport, tracker and tool invoker are real. The model choices
are fixed: this tests tool execution, not whether a language model follows an
injected instruction or understands consent. The recording creates no file or
customer record. No model-provider key is needed for the local exercise.

Start with the [guided exercise](tutorial/TUTORIAL.md). The website guide is
commissioned under `test-a-gate-against-split-mcp-payloads`; it is not yet a
published route. This pattern supplies that guide's runnable source.

## Install and check

Run these commands from `patterns/mcp-confirmation-gate` in the repository.
Use Python 3.12 and uv. Keep one environment for both variants:

```bash
uv sync --prerelease=allow --locked
RASA_TELEMETRY_ENABLED=false PYTHON_DOTENV_DISABLED=true \
  OPENAI_API_KEY=placeholder-not-a-real-key \
  uv run --locked python -m unittest discover -s tests -v
```

The suite must finish with `OK`. It checks the real MCP connection, native
confirmation rules, compiled configurations, cold archive loading, complete
turn loops and the REST channel. It starts and closes its own test services.
The tests make no model-provider requests; they do not require a Rasa licence.
That request count follows from the fixture and patched completion boundary;
it is not a network-capture result.

The archived-agent and REST controls also make the script attempt confirmation
in the same turn, supply a later boolean denial, and deliberately send the
wrong boolean after the user says no:

| Input to the real turn loop | What the check expects |
| --- | --- |
| Request the recording and resolve `true` in the same turn | The call remains pending and no recording runs |
| A later “No” with scripted `confirmed: false` | The call is cancelled and no recording runs |
| A later “No” with scripted `confirmed: true` | The recording runs: the engine trusts the model's boolean |

The last row is a limit control. Waiting for another user turn does not show
that a model interpreted the answer correctly. The gate protects a local tool
in this example; it is not attached to the MCP-imported case-reading tool.

If installation fails, check the Python version before changing anything.
Keep the lock and package pins unchanged when repeating this exercise.
If a test fails, preserve its traceback and identify the failed assertion.
Inspect the tool results as well as the assistant's wording. The guided exercise explains
how to read the tool results.

## Prepare a pair for the licensed CLI

The CLI needs a Rasa Pro licence. Set `RASA_LICENSE` in your shell without
putting it in source or shared logs. The fixed responses need only the fake
model key below. Run these commands from the pattern directory:

```bash
mcp_source="$PWD"
mcp_python="$PWD/.venv/bin/python"
mcp_runs="$(mktemp -d "${TMPDIR:-/tmp}/mcp-confirmation.XXXXXX")"
"$mcp_python" prepare.py --variant gated --run-dir "$mcp_runs/gated" --scripted-model-port 8938
"$mcp_python" prepare.py --variant ungated --run-dir "$mcp_runs/ungated" --scripted-model-port 8938
```

Keep this terminal open: it holds the paths for the next commands. Existing
destinations are refused. Each new directory contains source and a checksum
manifest, without an environment or credential file. The manifests must say
`"model_mode": "scripted-loopback"`.

The MCP service uses port 8937 and the model fixture uses 8938. Choose other
unused ports with `--mcp-port` and `--scripted-model-port` if needed, and use
those same ports when starting the services. Do not stop another process to
take its port.

Omitting `--scripted-model-port` deliberately selects the separate provider
configuration, which is outside this exercise and may make billable requests.

Train both projects using the same interpreter:

```bash
for variant in gated ungated; do
  (
    cd "$mcp_runs/$variant"
    OPENAI_API_KEY=placeholder-not-a-real-key \
      RASA_TELEMETRY_ENABLED=false PYTHON_DOTENV_DISABLED=true \
      "$mcp_python" -m rasa train
  )
done
```

Each command should save an archive in its project's `models` directory.
If licence validation fails, check the licence in your shell. Do not copy
credentials from another project or replace training with a claimed pass.

## Start the local services

In two other terminals, change to the pattern directory and run one command
in each:

```bash
.venv/bin/python mock_server.py --port 8937
```

```bash
.venv/bin/python scripted_model_server.py --port 8938
```

In the original terminal, start the gated project:

```bash
cd "$mcp_runs/gated"
OPENAI_API_KEY=placeholder-not-a-real-key \
  RASA_TELEMETRY_ENABLED=false PYTHON_DOTENV_DISABLED=true \
  LLM_API_HEALTH_CHECK=false LITELLM_LOCAL_MODEL_COST_MAP=True \
  "$mcp_python" -m rasa run --enable-api --interface 127.0.0.1 --port 5005
```

Wait for Rasa to report that it is serving requests. If an MCP or model port
is occupied, retain the failed runs and create a fresh run directory. Prepare
both variants there with new ports, retrain them and restart the fixtures on
those ports. Existing directories will not be overwritten.
If only Rasa's port 5005 is occupied, choose another with `--port` and update
the curl URLs below; that does not require preparing or training again.
The `gpt-4o-mini` name in the generated file only selects Chat Completions:
the fixture runs no GPT model and forwards no request to a provider.

## Read the tool results

From a fourth terminal, send the first message:

```bash
curl --fail-with-body -sS http://127.0.0.1:5005/webhooks/rest/webhook \
  -H 'Content-Type: application/json' \
  -d '{"sender":"gate-demo","message":"Read my fictional support case."}'
curl --fail-with-body -sS http://127.0.0.1:5005/conversations/gate-demo/tracker
```

Find the `record_local_canary` tool event. Its result must have
`"status": "awaiting_confirmation"`. The scripted request has reached the
engine, but the simulated operation has not run.

Send the second message with the same sender, then inspect again:

```bash
curl --fail-with-body -sS http://127.0.0.1:5005/webhooks/rest/webhook \
  -H 'Content-Type: application/json' \
  -d '{"sender":"gate-demo","message":"Yes, record it."}'
curl --fail-with-body -sS http://127.0.0.1:5005/conversations/gate-demo/tracker
curl --fail-with-body -sS http://127.0.0.1:8938/fixture-inspection
```

There should now be one `simulated_recording` result after the earlier pending
result. The fixture inspection shows `resolved: true` and no failures.
The script recognises the fixed positive phrase; it is not a general chat
model. The automated runtime tests supply the denial sequence separately;
typing arbitrary answers into this positive-only CLI fixture is a different
exercise.

If you see a connection error, check that all three services are running.
If the fixture reports failure, restart it before another trial: it holds a
single conversation's fixed decision sequence. Do not reuse it for multiple
senders or interpret its fixed replies as model behaviour.

## Compare with confirmation disabled

After the curl commands finish, use Ctrl+C in the Rasa terminal. Stop and
restart the scripted model service to reset its sequence. The MCP service can
remain running. In the original terminal, change to `$mcp_runs/ungated` and
repeat the same Rasa startup command. Send only the first message, using a
fresh sender such as `ungated-demo`, and read that sender's tracker.

Its first recording result should be `simulated_recording` immediately.
The source variants differ only in the confirmation flag; their fixture
endpoints and tool functions match.

Stop your own Rasa and fixture terminals with Ctrl+C when finished. Retain any
failed-run evidence before removing the generated run directories. No second
Python environment is needed. Normal CLI interrupt cleanup was observed on
macOS Arm64; that is not a guarantee for every signal or platform.

## Limits and evidence

The positive phrase causes the script to supply boolean confirmation. This
does not show informed consent or the accuracy of a real model's decisions.
Backend permissions, identity, current values and real write effects need
their own checks. This text example does not test voice, ASR, TTS or barge-in.

The current 22-test run and both licensed CLI variants are recorded in
[`qualification-runtime.json`](qualification-runtime.json), bound to tested
source `0261a7f82410463377df13d070be49d88303860a`. The receipt includes the
fictional HTTP replies and tool results. Its zero provider-request count is
derived from the local fixture and completion patch, not a network capture.

Historical source-bound CLI results are in `qualification-cli.json`. They are
maintainer attestations with archive and log hashes, not self-contained HTTP
transcripts. An empty CLI log contains no HTTP response body. The automated
runtime controls check those returned results.
Earlier prototype checkpoints remain in Git history, although they are absent
from the current tree. Each receipt applies to the inputs and scope it names.

Teaching source follows the repository's [Apache 2.0 licence](../../LICENSE).
Rasa Pro has its own licence and terms.
