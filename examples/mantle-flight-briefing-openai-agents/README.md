# Brief me before I fly — work in progress

Author: Mator Clawson
Assessed on: not_provided
Assessed by: not_provided
Verified with: Python 3.12.13 source/replay controls; Mantle end-to-end not verified
Audience: Practitioners connecting a Mantle conversation to a managed specialist
Time: not_provided — reader exercise not accepted yet

**Not ready as a complete example.** The Core-backed replay, authenticated MCP
request path and fixed text-card renderer have passed author controls. The
pinned Mantle package does not yet implement the hook-to-MCP metadata path
described in its current documentation. An owning-engine contribution or a
qualified version containing that path is required before this is a working
Mantle conversation. Do not remove identity checks to make it run.

The product imports exactly one MCP tool,
`briefing(action=start|get|revise, request?, job_id?, change?)`. The authenticated
Mantle peer and engine sender identify the conversation outside model arguments.
Core supplies widget validation, per-widget supersession and the managed Agents
API wrapper. Model output never supplies the numbers in the cards.

## Current offline checkpoint

`Replay DEMO101` is constructed classroom data, not an actual flight or a provider
recording. `Replay DEMO101 later arrival` changes the arrival estimate and margin.
`Replay DEMO101 morning weather` updates only weather, preserving the flight and
timeline cards with their own provenance. Every visible card says REPLAY. The
90-minute transfer is an assumption, never traffic. Missing provider update time
is distinct from retrieval time.

The backend uses Core's `ScriptedTransport` and actual callback loop. No remote
agent, weather/flight provider, voice system or model is exercised by those tests.
The current presentation fallback is fixed text cards in the conversation; it
is not native Mantle arbitrary widgets or an interactive chart renderer.

## Dependency custody and checks

The dev Core wheel is not a public release. Its source and expected bytes are in
[`worker/core-artifact.json`](worker/core-artifact.json). A supported carrier must
stage that exact wheel into `worker/inputs/` and verify its hash before setup.
The same input is used by both resource-owned locks. Never substitute a package
with the same version label but different bytes.

Create each environment through the repository's managed helper, from repository
root, after the verified input is available:

```sh
python3 scripts/workspace.py start examples/mantle-flight-briefing-openai-agents/worker --owner flight-worker
python3 scripts/workspace.py start examples/mantle-flight-briefing-openai-agents/project --owner flight-mantle
examples/mantle-flight-briefing-openai-agents/worker/.venv/bin/python -m unittest discover -s examples/mantle-flight-briefing-openai-agents/tests -v
```

These checks include the actual MCP ASGI path in process without a listening
server, cross-conversation refusal and source-card replay. They do not prove
Mantle metadata propagation or the live product.

## Runtime boundary

The facilitator-only local launcher is `python -m briefing` from this directory,
using the worker interpreter. It requires the same runtime-only
`BRIEFING_MCP_TOKEN` in the launcher and Mantle processes. Do not put its value in
a file or log. This launcher starts a loopback service and is not a source-only
test. The current default backend is constructed replay only.

Actual model/provider access uses only the facilitator's own environment. No
key belongs in this repository, seat mail or a file written by a seat. Live
flight schedules need their own verified provider access. No live API, real
flight lookup or voice success is claimed here.

The remaining acceptance is an observed Mantle conversation calling this tool,
showing the validated cards and preserving conversation isolation, followed by
independent Ops acceptance. Syntax checks, unit tests and this draft PR do not
complete that outcome.

Teaching source follows the repository [license](../../LICENSE); Rasa Pro has
its own distribution and licensing terms.
