# Feature specification v3: "Brief me before I fly" (spec owner: rasa-ops)
sow: software-factories-masterclass-SOW-02
v3 locked Wed 21 Oct 2026 12:5xZ. v3 changes ONLY section 3 (one MCP tool, chosen by rasa per the operator's one-tool direction) and the matching pack skill; every scenario keeps its meaning. v2 (sha256 5330a60628e773926615cc1db4a27a323462a60e8879bd68494ab81b6180e8da) and v1 (sha256 0dbfeb92c64cadf044f5046c1e16ca288fa14d8b751ab0d1b8c683d4e69dbb78) are superseded; the 12:22Z desk-widgets plan too.
v2 text follows. Supersedes v1 (sha256 0dbfeb92c64cadf044f5046c1e16ca288fa14d8b751ab0d1b8c683d4e69dbb78) and the 12:22Z desk-widgets plan.
CHANGES FROM v1 (operator change of 12:3xZ, brief v2 sha256 d6863de69dd7767c47a1c3851ec3ff01fb70e6cd124464d9391c0cf41662d5b5, Architect msg-architect-20261021T123723Z-081ee3):
 1. NO separate browser dashboard. The product is a Rasa Mantle agent whose answers carry zeocore-defined widget cards, rendered where Mantle's conversation is shown. Use whatever Mantle renders natively first; a thin client-side renderer only for what it does not; never claim a Mantle widget feature that does not exist.
 2. Mantle is the centre: skills, flows, MCP imports, responses, voice and its own testing. The OpenAI Agents API is the specialist behind a Mantle-imported MCP tool. The dark factory is how the Mantle agent is built and extended.
 3. Order: a complete working end-to-end experience first, rehearsed; then the pack breaks it into step-by-step increments.
 4. Provider timestamps: a missing provider update time is represented as unknown, never filled from fetched_at (data_ref.as_of is nullable; see section 4).
SETTLED in v3: one tool, briefing, with an action argument.
Companion: ACCEPTANCE-SCENARIOS-v1.md (kept apart from the implementation; the builders never receive it as code to edit). Schemas: widget-upsert.schema.json, data-ref.schema.json.

## 1. Purpose
A user speaks a travel request. Mantle converses; one OpenAI Agents API session (beta.agents, never the openai-agents SDK) investigates behind the MCP tool; the briefing service validates results; the Mantle answer carries widget cards defined by zeocore and shown where the conversation is shown. The cards carry the detail; speech stays short.
Core story (act 1): flight status, arrival weather, arrival timeline. Second act: market watchlist, added by a coding agent from this spec inside the factory.

## 2. Components and ownership
- Mantle: conversation, clarification, skill routing, spoken responses. Imports the three MCP tools (mcp_servers in integrations.yml, import_tools in the skill).
- Briefing service (MCP server): the one tool briefing(action=start|get|revise). Owns the mapping conversation -> briefing job -> OpenAI session.
- OpenAI Agents API: multi-source investigation and synthesis. Never asked to produce numbers; numbers come from data_refs.
- Data adapters: fetch and normalise provider data (flight, weather, market). Each result becomes a data_ref with provenance.
- Widget cards: four predefined components defined by zeocore, carried in the Mantle answer and rendered in the conversation surface. Rendering is native Mantle where it exists; a thin client-side renderer covers the rest. Mantle has no documented arbitrary MCP widget rendering; say so.
Owners: rasa-ops = this spec, the acceptance scenarios, the pack text; rasa = the Mantle agent project, briefing service, adapters and any thin renderer; zeocore = Agents API support and widget-routing types.

## 3. MCP interface (ONE task tool; the model never supplies a session or user identifier)
briefing(action, request?, job_id?, change?) with action in start | get | revise and strict per-action argument validation:
- action=start, request: str -> {job_id, status: "started"} promptly; the work continues in the background.
- action=get, job_id -> {status: started|running|needs_input|complete|incomplete|failed, progress: [..], needs_input?: {field, question}, widgets: [widget_id..], reason?}
- action=revise, job_id, change: str -> {job_id, status, revision}. Applies a follow-up to the existing job (new destination, new time, "refresh", "compare").
Any other argument combination is refused. Internal start, get and revise service functions may remain. The service resolves the job through the authenticated conversation. A job_id belonging to another conversation is refused.
Completion is established by inspecting the saved turn and tool results, never by a stream ending.

## 4. Widget registry (closed): flight_status, weather_hourly, arrival_timeline, market_watchlist
Event (carried with the answer): {type:"widget.upsert", request_id, widget_id, component, data_ref, revision}. Same widget_id replaces the card where the surface can update in place; where it cannot, the newer card is shown as superseding and the older is marked superseded. A lower or equal revision is ignored.
data_ref (provenance, see schema): id, source, fetched_at (when we retrieved it), as_of (the provider's own update time, or null when the provider gives none; never copied from fetched_at), replay (bool), delayed (bool|null), assumptions[] (each {label, value, kind:"assumption"}), payload (component data), error? .
Numbers, times and labels shown or spoken come from payload. Components accept only their declared payload shape; no HTML, no script, no URLs in values.

## 5. Component payloads (minimum)
- flight_status: flight_number, route {from, to}, scheduled_departure, estimated_departure (nullable), scheduled_arrival, estimated_arrival (nullable), terminal (nullable), reported_status (provider's own string), source timestamp. "Delayed" is never computed by us; it is only repeated from reported_status.
- weather_hourly: location, timezone, valid_from/valid_to, hourly[{time, temp_c, precip_prob, precip_mm}], arrival_hour marker.
- arrival_timeline: steps[{label, time}], transfer_minutes with kind:"assumption" (stated, never traffic), meeting_time, margin_minutes (computed from payload values by the service, shown with its inputs).
- market_watchlist (act 2): symbols[{symbol, price, change, change_pct}], market_status, quote_time, delayed (true when the provider says so), series for charts.

## 6. Honesty rules (said aloud in the session; tested)
1. The widget cards are defined by zeocore and drawn by our renderer where Mantle does not render them natively; they are not a Mantle feature.
2. Replay data is labelled replay on the card and in speech.
3. A transfer time is an assumption, never live traffic.
4. Delayed market data is labelled delayed and never called real time.
5. A failed source shows an explicit unavailable state with its reason; no stale value is shown as current.
6. A missing provider field is shown as "not provided"; a missing provider update time is shown as "provider update time not given" beside the retrieval time.

## 7. Modes
- Default demo: labelled replay data, complete and rehearsed offline.
- Live: facilitator laptop only, keys in the facilitator's own environment (api.agents.read, api.agents.write, api.responses.write). No key in a repository, seat, mail or file a seat writes. A flight provider with schedules may need its own key; availability is proven before a live flight demo is promised.
- Outbound-MCP limit: the Agents API calls MCP tools from OpenAI's side, so a localhost endpoint is unreachable; rasa and zeocore state the chosen route before building around it (reachable authenticated endpoint, function tools in the session, or the service calling the adapters itself). Proposed by rasa (ans_b228308f83bc79d0, to be confirmed by zeocore): application-handled function tools in agent.tools, with the allowlisted names and arguments validated and executed locally and the result returned as agent.session.input.tool_result; no public ingress.

## 8. The factory, second act (market watchlist)
Baseline checkpoint = act 1 accepted. Input to the coding agent = this spec sections 3 to 6 for market_watchlist, the data_ref schema, the existing component and adapter examples (flight, weather), and a build and preview command. Protected acceptance = ACCEPTANCE-SCENARIOS-v1.md scenarios M1 to M4 plus the core scenarios S2, S3, S5, S6; the coding agent may not edit acceptance, the registry entries of other components, or the flight and weather adapters. Release gate = observed behaviour through Mantle in the browser. Evidence of completion = the new card appears from a spoken request, with its source, timestamp and acceptance results shown. A completed checkpoint exists for fallback.

## 9. Out of scope / not claimed
Real traffic or transit data; trading advice; any claim a model follows wording; Mantle-native widgets unless a Mantle page documents them; ZEOconnect (not used anywhere).
