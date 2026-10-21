# Brief me before I fly — work in progress

Author: Mator Clawson
Assessed on: not_provided
Assessed by: not_provided
Verified with: Python 3.12.13 replay/MCP controls and pinned Mantle hook adapters and tracker/channel delivery; full conversation not verified
Audience: Practitioners connecting a Mantle conversation to a managed specialist
Time: not_provided — reader exercise not accepted yet

**End-to-end qualification is pending.** The Core-backed replay, authenticated
MCP request path and fixed text-card renderer pass author controls. The class
uses the Architect-approved capability-ID fallback because published Mantle
packages through 3.21.0 do not forward engine identity as MCP metadata. No engine
patch or fork is required by this fallback.

The product imports exactly one MCP tool,
`briefing(action=start|get|revise, request?, briefing_id?, change?)`. Start returns
an unguessable ID with 256 random bits. Get and revise require possession of that
ID and an authenticated Mantle peer. Missing or wrong IDs are refused; there is
no enumeration tool. **Anyone with the actual ID and peer access can read or
revise the briefing, including another conversation.** This is capability
possession, not engine-sender isolation. Keep IDs out of shared transcripts,
logs and telemetry. Standard and structured application logs redact the ID pattern; do not
configure request-body/access tracing that would capture tool arguments.

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
examples/mantle-flight-briefing-openai-agents/project/.venv/bin/python -m unittest discover -s examples/mantle-flight-briefing-openai-agents/tests -v
```

These checks include the actual MCP ASGI path in process without a listening
server, missing/wrong capability refusal, deliberate access with a valid capability
from another conversation, and source-card replay. They do not prove the live
Mantle conversation or provider access. The project interpreter additionally
exercises the actual pinned Mantle hook loader and runner with constructed Core
results: it shows source-backed cards, preserves an unaffected timeline across a
weather revision, and suppresses unchecked model numbers when cards are invalid.
The engine adapters receive the same serialized JSON result that real MCP
dispatch produces. The wired model-response modifier replaces free-form numbers
before the real turn context records and delivers the cards. The pin registers
`outgoing_text` but does not invoke it during delivery, so this project does not
use that hook. That is adapter and delivery integration evidence, not a complete
model-driven conversation or a proof of streaming behavior.

A separate keyless conversation control runs the actual Mantle orchestrator,
skill dispatch, MCP ClientSession/server, Core replay, hooks, tracker and output
channel. Only the LLM provider factory is replaced with scripted responses over three turns
(initial briefing, weather-only revision, later arrival); the HTTP transport stays in process. This proves
that those pieces connect, that the weather follow-up retains the original
flight/timeline provenance, and that a later arrival changes the margin from
120 to 30 minutes while unchecked model numbers are replaced. The
script chooses the capability from fixture state; it does not prove a model can
retain it, follow the skill or interpret a traveller’s request. No installed
engine file is changed. Real model behavior and facilitator acceptance remain
outstanding.

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
showing the validated cards and demonstrating the documented capability boundary, followed by
independent Ops acceptance. Syntax checks, unit tests and this draft PR do not
complete that outcome.

Teaching source follows the repository [license](../../LICENSE); Rasa Pro has
its own distribution and licensing terms.
