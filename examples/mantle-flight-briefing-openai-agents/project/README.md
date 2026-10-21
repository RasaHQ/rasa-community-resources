# Mantle flight-briefing conversation — unqualified draft

Author: Mator Clawson
Assessed on: not_provided
Assessed by: not_provided
Verified with: rasa-pro 3.21.0.dev5 actual hook adapters and tracker/channel delivery; full conversation not verified
Audience: Maintainers qualifying the flight-briefing conversation
Time: not_provided

Read the [resource status and setup](../README.md) first. This project uses the
approved capability-ID fallback: start returns a private `briefing_id`; get and
revise require it. A conversation without that ID is refused. A conversation
with the actual ID can access the briefing. There is no engine-sender binding,
listing operation, engine patch or fork. The skill instructs the model to retain the ID in tool context; this is a prompt
instruction, not enforced retention. The wired model-response modifier redacts
capability-shaped text from replies while preserving tool arguments. Real model
retention and tool selection still require the facilitator rehearsal.

The pinned engine reads `llm.model_group` from `integrations.yml`. Its current
public documentation's dynamic MCP metadata hook is absent from this pin and
from all nine newer published versions inspected through 3.21.0. That upstream
capability is a separate future contribution, not a prerequisite for this path.

Presentation uses the engine-wired tool-result and model-response modifiers.
The latter replaces unchecked model prose with validated source cards before
non-streaming delivery. It does not rely on the uninvoked outgoing-text hook.
Streaming and the complete model/tool conversation still require qualification.

The lock points to the verified dev Core wheel in `../worker/inputs/`, not a
registry release. Source controls do not establish a Mantle conversation,
widget rendering, voice or a live Agents API result. No assessment date or
assessor is supplied until the intended workflow is qualified.

Environment variable names are listed in `.env.example`; values must remain
only in the facilitator's own runtime environment. The doctor reads only process
environment values. For engine dotenv controls and their limits, see below.

## Facilitator runtime checkpoint

For a **keyless scripted demo**, run from the example directory after verifying the committed Core wheel checksum and managed
setup:

```sh
project/.venv/bin/python scripted_demo.py
```

This one command runs the same checked ten-turn actual Mantle/MCP/Core harness
and prints the delivered cards and questions. It needs no model key, user input
or listening server. The output says SCRIPTED / CONSTRUCTED REPLAY: provider
responses and capability selection are scripted. It is a classroom replay,
not proof that a model understands requests, retains IDs or selects tools. A
failed assertion stops the launcher without presenting a successful transcript.

For the **facilitator's real-model conversation**, use the two-shell path below.
After managed setup, use two facilitator shells with the same runtime-only
`BRIEFING_MCP_TOKEN` (at least 32 characters) and the facilitator’s own
`OPENAI_API_KEY`. Supply those through the facilitator’s existing environment;
do not save them into `.env` or a transcript. This is a runtime exercise, not a
source gate; it starts services and makes model calls.

From the example directory, start the constructed replay backend:

```sh
worker/.venv/bin/python -m briefing
```

From this `project/` directory in the second shell:

```sh
export LITELLM_MODE=PRODUCTION
.venv/bin/rasa train
.venv/bin/rasa inspect
```

These are the installed engine’s normal entry points, not an assertion that
this complete launch has passed. Use the named constructed replay explicitly:
“Show the constructed Replay DEMO101.” Expect flight, weather and timeline text
cards, REPLAY labels, a 90-minute assumed transfer, and a 120-minute margin. Then
ask for “Replay DEMO101 morning weather”; flight and timeline must retain their
provenance. A later-arrival revision must replace the affected values. Do not
supply a real journey to this replay-only backend or accept invented live facts.

Never disclose the briefing capability in the reply. Check the missing/wrong-ID
refusal and explain that sharing the real ID grants access. A successful launch
is still subject to the independent class acceptance checks. Stop both runtime
processes when the exercise is finished.

## Participant keys and one doctor command

Participants bring no keys. The facilitator hands out OpenAI and Anthropic keys
in class and shows how to set process environment variables privately. Do not
paste them into chat, terminal recordings, this repository, `.env`, logs or
notebooks. The doctor does not load `.env`; names-only `.env.example` is documentation.
The engine is a separate dependency: launch it with `LITELLM_MODE=PRODUCTION`
to disable LiteLLM development dotenv loading. This is not a certification of
every third-party configuration loader.
`.env`, `.env.*`, `.envrc` and `*.key` are git-ignored. No OAuth, ZEOconnect or
account login is used by these paths. Seats never receive a key.

Choose the live Mantle provider with **one setting** in `integrations.yml`:
`llm.model_group: openai` or `llm.model_group: anthropic`. Both declared groups
reference environment variables rather than literal keys. The doctor refuses
custom `OPENAI_BASE_URL` / `ANTHROPIC_BASE_URL` overrides and unusably short
keys without printing their values; use provider defaults for the class.

| Path | Environment key required | Data / remaining proof |
| --- | --- | --- |
| Mantle OpenAI (`gpt-4.1-mini`) | `OPENAI_API_KEY` | Real conversation over constructed replay; facilitator live proof pending |
| Mantle Anthropic (`claude-sonnet-5-5`) | `ANTHROPIC_API_KEY` | Same constructed replay; facilitator live proof pending |
| OpenAI managed Agents leg | `OPENAI_API_KEY`, even with Anthropic Mantle | SDK/Core compatibility and facilitator live proof still pending |
| SCRIPTED ten-turn fallback | neither | Provider responses/capability choice scripted; no model reasoning claim |

From the example directory, on each participant machine:

```sh
project/.venv/bin/python class_doctor.py
```

It prints only `SET` or `MISSING` for each key name and the selected live path.
With neither key and no live probe requested, SCRIPTED is a valid ready state
and exits zero without a refusal or network call. Explicit live probes still
refuse a missing selected key. If only the other provider key is set, selected
provider readiness remains refused. To check the fallback:

```sh
project/.venv/bin/python class_doctor.py --scripted
project/.venv/bin/python scripted_demo.py
```

After the facilitator privately sets the selected provider's key in their own
process environment, they can make one bounded smoke call through Mantle's
actual configured provider client:

```sh
project/.venv/bin/python class_doctor.py --probe
```

Repeat after changing `llm.model_group` to the other provider. The command prints
only path and `PROBE: PASS` or a generic failure, never response content, key
values or exception diagnostics. No key or raw log is sent to a seat. Report
only provider, source head, pass/failure, and whether the actual conversation
rehearsal passed. A smoke call is not full conversation acceptance.

`--probe-agents` separately targets Core's managed OpenAI Agents adapter. The
current Mantle lock pins SDK 2.44, which lacks `beta.agents`; SDK 3.36 has that
namespace but also needs a Core stream-identity compatibility change. This is
an explicit outstanding dependency, not a working live-leg claim or a reason
to replace Agents with another API. The probe refuses unsupported runtimes;
no SDK upgrade or alternate transport should be improvised in the class.
The labelled scripted fallback remains available.

Provider references: [OpenAI environment-key quickstart](https://developers.openai.com/api/docs/quickstart),
[managed Agents API contract](https://developers.openai.com/api/docs/guides/agents-api/quickstart),
and [Anthropic Sonnet 5.5 model identity](https://platform.claude.com/docs/en/models/sonnet-5-5/overview).
These establish interfaces/model names, not access for a handed-out key.

## 7. Facilitator live check (15 minutes)

Use the exact source head linked for this run; this checks real Mantle over
constructed briefing data, not a live flight/weather provider. The managed
OpenAI Agents leg remains NOT_RUN until its SDK/Core compatibility work is
received. Keep all keys in the facilitator's process environment. Send no keys,
raw logs or transcripts to a seat.

1. From the example directory, set `export LITELLM_MODE=PRODUCTION`, then run `git rev-parse HEAD` and
   `project/.venv/bin/python class_doctor.py --scripted`. The head must match the
   linked run candidate; see both key names with SET/MISSING and PATH: SCRIPTED.
   Missing keys are expected before they are handed out. The managed worker and
   project environments and committed wheel must already be installed.
2. With the facilitator's own OpenAI key privately set in OPENAI_API_KEY, select
   `llm.model_group: openai` in `project/integrations.yml` and run
   `project/.venv/bin/python class_doctor.py --probe`. Expect PATH: live OPENAI
   Mantle and PROBE: PASS, without a key value or response dump. A failure stops
   this live path; it is not a successful conversation proof.
3. With the facilitator's own Anthropic key privately set in ANTHROPIC_API_KEY,
   change that same setting to `anthropic` and repeat the doctor --probe command.
   Expect PATH: live ANTHROPIC Mantle and PROBE: PASS. Choose either successful
   group for the conversation. Do not save either key into a file.
4. In the same parent terminal, create an unprinted loopback transport token,
   start the constructed backend, and launch the ordinary Mantle inspector:

   ```sh
   export BRIEFING_MCP_TOKEN="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
   project/.venv/bin/python -m briefing &
   briefing_service_pid=$!
   (cd project && .venv/bin/rasa train && .venv/bin/rasa inspect)
   ```

   Expect the inspector conversation and the local backend; no live provider
   observation is claimed by the backend. This terminal alone owns its token
   and child process; do not print or copy environment values.
5. In the inspector send these messages in order: `Show the constructed Replay
   DEMO101` (three REPLAY cards, 120-minute margin); `Replay DEMO101 morning
   weather` (flight/timeline unchanged); `Replay DEMO101 later arrival`
   (30-minute margin); `Replay DEMO101 missing inputs` (meeting question);
   `tomorrow at five` (question repeated); `2026-10-22T21:00:00Z` (transfer
   question); `45 minutes` (165-minute margin); `Replay DEMO101 flight
   unavailable` (incomplete, weather retained, no stale margin); `Replay DEMO101`
   (recovery, 165-minute margin); `Replay DEMO101 no estimate` (scheduled arrival
   labelled, absent estimate, 195-minute margin). A real model must choose the
   offered tool and retain the private ID itself; stop and record any mismatch,
   invented number or displayed credential rather than calling it a pass.
6. Stop the inspector, then run `kill "$briefing_service_pid"` in its parent
   terminal. Return only source head, selected provider, each probe PASS/FAIL,
   and redacted observations for the sequence. If a key or capability appeared,
   report the channel and failure without its value. If live setup fails, run
   `project/.venv/bin/python scripted_demo.py`: expect ten labelled SCRIPTED
   turns, explicitly record that fallback rather than real-model success.
