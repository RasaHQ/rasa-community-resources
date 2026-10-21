# Optional live model, constructed source fixtures

sow: flagship-resources-SOW-01

This follow-on uses the real managed Agents model path with the same validated,
explicitly labelled constructed flight and weather fixtures. It does not call
live flight or weather providers. Model prose never supplies delivered card
values. Only named `Replay DEMO101` scenarios are supported here.

The class's default `worker` stays on Core dev17. Mantle's `project` stays on
OpenAI 2.44.0. The separate `live-worker` pins OpenAI 3.29.0 and Core dev20
(`e271d9d4fa01ba8ea2a83e5b2eba03b587675ee4a317f638d41fb2a3a04f3fbe`).
Wheel publication and adoption require Council's independent source comparison
MATCH under the Architect's conditional pin. Preparation is not that verdict.

After that gate, from the repository root:

```sh
python3 scripts/workspace.py start examples/mantle-flight-briefing-openai-agents/live-worker --owner facilitator-live-agents
```

Then, from `examples/mantle-flight-briefing-openai-agents`, the facilitator
privately sets `OPENAI_API_KEY` and `BRIEFING_AGENTS_MODEL` for a model their
account can use. Do not put a key in command arguments, files, logs or MCP
metadata. The existing runtime-only `BRIEFING_MCP_TOKEN` must be supplied to
the service and its Mantle peer. No credentials are requested from participants
or from another seat.

The live launcher refuses a nonblank `OPENAI_BASE_URL` or `ANTHROPIC_BASE_URL`
before constructing a client or opening the listener, without printing its
value. This kit uses only the providers' default endpoints.

```sh
live-worker/.venv/bin/python class_doctor.py --probe-agents
live-worker/.venv/bin/python -m briefing --live-model
```

The first command makes an explicit live facilitator smoke request. It refuses
plainly before a provider request if the client lacks `beta.agents.sessions`.
The second starts the existing localhost-only MCP service using a live model;
it requires the facilitator's explicit choice. Mantle and the authenticated MCP
capability boundary are otherwise the same as the scripted example. Neither
command is part of a keyless test or automatically run during setup.

Every native revision starts a new managed session containing the prior
validated source brief. It does not resume the legacy stream-per-post adapter
or carry unchecked model prose. Core bounds requests, events, time and callback
sizes/counts. Native callbacks expose tool names, not call IDs, so this mode
does not claim application-level `(turn_id, call_id)` deduplication. A failed
native turn or a model that omits the source callbacks cannot complete a job.
The existing request/revision fence prevents late results from replacing a
newer view. Cancellation of a Python thread is not a hostile-process isolation
boundary; Core's finite native deadline remains required.

The default service command and the guaranteed class script remain unchanged:

```sh
worker/.venv/bin/python -m briefing
project/.venv/bin/python scripted_demo.py
```

Offline fake-client tests check the resource integration and failure paths.
They are not a live model, provider, voice, final-main cold-clone or classroom
acceptance. The facilitator's first live check remains separate.
