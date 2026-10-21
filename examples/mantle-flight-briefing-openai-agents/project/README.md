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
listing operation, engine patch or fork. The skill keeps the ID in tool context
and must not disclose it in the user-facing reply.

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
only in the facilitator's own runtime environment. No file is loaded by this
project to discover credentials.

## Facilitator runtime checkpoint

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
