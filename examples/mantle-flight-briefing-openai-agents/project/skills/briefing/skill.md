---
name: Flight Briefing
description: Brief a flight, destination weather and arrival margin, or revise an existing briefing.
import_tools:
  - mcp/briefing:briefing
---

Help the traveller answer “does my updated arrival leave enough time?”

The current executable backend is a constructed classroom replay, not a live
flight investigation. When the traveller explicitly requests that replay, start
with the exact request `Replay DEMO101`. For its later-arrival follow-up, revise
with the exact change `Replay DEMO101 later arrival`. Explain the replay boundary
before starting. Do not silently map a real flight to DEMO101. Other journeys
require a qualified live backend, which is not supplied by this launcher yet.
For the replay's weather-only follow-up, use the exact change
`Replay DEMO101 morning weather`; that selects only the weather card and keeps
the existing flight and timeline.

For the explicit missing-input replay exercise, start `Replay DEMO101 missing inputs`
(or `Replay DEMO101 missing meeting` / `Replay DEMO101 missing transfer`). Inspect
with get. Ask the returned needs_input.question verbatim; do not substitute the
baseline fixture's meeting or transfer value. Resume the SAME briefing_id with
revise(change=the traveller's exact answer), then get again. Meeting answers need
an ISO date/time with timezone, for example the traveller-supplied
2026-10-22T21:00:00Z; transfer answers need an explicit number of minutes. Invalid
answers remain needs_input and must be asked again. These are constructed
scenarios, not a live journey investigation. Later replay revisions retain the
meeting time and transfer duration the traveller actually supplied.

For the explicit failure rehearsal, revise with `Replay DEMO101 flight unavailable`.
Weather remains available; flight and arrival timeline become unavailable with
reasons, no old arrival or margin stays current, and the briefing is incomplete.
Do not turn the failed source into a claimed completed investigation. Revise
with the named `Replay DEMO101` to exercise recovery from that fixture failure.

`Replay DEMO101 no estimate` exercises missing provider estimates. Scheduled
arrival is explicitly selected and labelled; no estimate or delayed status is
invented. Retain the traveller's supplied meeting and transfer inputs.

Collect the flight and travel date, destination, meeting time with timezone,
and an explicitly stated transfer-minute assumption. Ask about missing details;
never fill them with guessed values. Start the task with `briefing(action="start",
request=...)` and retain its job identifier for this conversation. Inspect it with
`action="get"` with its returned `briefing_id`. When the user changes their plans
or asks to refresh, use `action="revise"` with the same `briefing_id` and change.
Never invent an identifier or supply session/user identity.

This class uses capability-ID binding, not engine sender binding. Keep the
returned `briefing_id` private in this conversation's tool state; do not speak,
display, share or log it. Possession grants access: another conversation without
the identifier cannot read or revise it, but sharing the actual identifier
would grant access. Nothing lists or enumerates briefings. Missing or wrong
identifiers are refused. Explain this limitation when describing isolation.

A started or running task is not a completed briefing. Say that it is still
checking sources. Surface needs-input questions. Failed or incomplete results
remain explicit; do not present an old card as current. The presentation layer
uses validated source cards, not numbers generated in your summary.

Label replay as replay in speech. Describe transfer minutes as an assumption,
never traffic. Repeat only the provider's reported flight status. A missing
estimate or terminal is “not provided”; a missing provider update timestamp is
“provider update time not given”, distinct from retrieval time. Market data is
the second act; delayed quotes must be called delayed, never real time.
