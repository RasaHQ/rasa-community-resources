# Acceptance scenarios v4 for "Brief me before I fly" (owner: rasa-ops; kept apart from the implementation)
sow: software-factories-masterclass-SOW-02
Locked with SPEC-brief-me-before-i-fly-v4.md; only S10 changed from v3 (capability fallback, Architect ans_a6bd4821323124d5). Scenario meanings are unchanged from v2; the tool is now the single briefing(action=start|get|revise) (v2 sha256 8ad308b3ee617c56730f54aa3fa1a356f0f2b51e74b181df02cb3e1819d3483b; v1 ( sha256 d71981eec8bf0612047f401e3932addd56bc3fd2d36d0deb46dbb59eb6841f2a). Each scenario is stated against the public contract only (MCP tools, widget.upsert events, data_ref); none reads implementation internals.
Tag: [core] act 1, [m] act 2 market, [manual] rehearsal check, not automatable offline. All automatable scenarios run on labelled replay fixtures; live mode is a separate dated check, never a substitute.

## Core (act 1)
S1 [core] Fast start. GIVEN a conversation, WHEN briefing(action=start) is called, THEN it returns a briefing_id and status "started" before any widget data exists, and briefing(action=get) reports progress entries in order (flight, weather, timeline).
S2 [core] One live card per widget_id. GIVEN a widget.upsert for widget_id W at revision 2, WHEN another for W arrives at revision 3, THEN the conversation surface shows revision 3 as the live card for W (updated in place, or shown as superseding the older card where in-place update is not possible); a later event at revision 2 or lower is ignored.
S3 [core] Provenance on the card. GIVEN any rendered card, THEN it shows source and fetched_at from its data_ref, and as_of when the provider gave one; when as_of is null it says "provider update time not given" and never shows fetched_at as the provider's time, and every number, time and label on the card equals the payload value (no value typed by the model).
S4 [core] Partial failure. GIVEN the flight adapter fails, WHEN weather succeeds, THEN the weather card renders, the flight card shows "unavailable" with the reason, and no earlier flight value is shown as current.
S5 [core] Destination change race. GIVEN a weather request for city A is running, WHEN briefing(action=revise) changes the destination to city B and A's result arrives afterwards, THEN A's result is discarded and the weather card for B is unchanged.
S6 [core] Replay is labelled. GIVEN any data_ref with replay=true, THEN the card shows a visible replay label and the spoken answer says the data is replayed.
S7 [core] Transfer time is an assumption. GIVEN the user asks whether the updated arrival leaves time for a 17:00 meeting, THEN the arrival_timeline shows transfer_minutes labelled "assumption", margin_minutes is computed from payload values, and neither the card nor the speech says traffic or live. The arrival used is estimated_arrival when the provider gave one, otherwise scheduled_arrival, and the card says which (S7a estimated present, S7b estimated null).
S8 [core] Missing input is asked, not guessed. GIVEN the meeting time or transfer assumption is missing, WHEN briefing(action=get) runs, THEN status is needs_input with the field and question; Mantle asks it; the job resumes when answered.
S9 [core] Status words are the provider's. GIVEN a flight data_ref, THEN the reported status shown or spoken equals reported_status; "delayed" appears only if that string says so; scheduled and estimated times are shown separately; a null estimate or terminal shows "not provided", never a guess.
S10 [core] Capability isolation. GIVEN a briefing started in conversation X (start returned briefing_id), WHEN briefing with action get or revise is called from conversation Y WITHOUT that id, or with a missing or wrong id, THEN it is refused and nothing changes in X; no call lists or enumerates briefings; the id appears in no log in clear. Stated boundary: a caller that holds the actual id CAN read and revise (possession); isolation is not by engine sender identity, and the spoken and written text never claims it is.
S11 [core] Completion is inspected. GIVEN the OpenAI session stream ends without a saved outcome or with a failed tool result, THEN briefing(action=get) returns incomplete or failed, never complete.
S12 [core] No secrets. GIVEN the repository, fixtures, logs and recorded outputs, THEN none contains an API key or token pattern.
S13 [manual] Voice and cards share one conversation. GIVEN a spoken weather request to the Mantle agent, THEN the matching card appears in that conversation only. This is the main integration risk; rehearse it, state the evidence level aloud.
S14 [manual] Live mode. GIVEN the facilitator's own key, THEN one request completes through zeocore and the Agents API. NOT_RUN labelled if unavailable; the replay demo is the default.

## Act 2: market_watchlist (added by the coding agent)
M1 [m] Delayed is labelled. GIVEN a quote data_ref with delayed=true, THEN the card shows "delayed" with quote_time and the spoken answer never says real time or live.
M2 [m] Symbols are configured. GIVEN a symbol not in the configured watchlist, THEN no row is added and the user is told it is not on the list.
M3 [m] Compare uses data. GIVEN "compare the first two", THEN the figures shown come from the two payload rows, not recomputed by the model.
M4 [m] Registry closed. GIVEN the coding agent's change, THEN the registry still holds exactly four components, flight and weather adapters are byte-identical to the baseline, and the acceptance files are unchanged (checked by hash).
M5 [m] Market status. GIVEN market_status is closed, THEN the card says closed and shows the last quote time, not the current time.

## Factory gate
ACCEPT only if S2, S3, S5, S6, M1 to M5 pass offline on the candidate. The browser observation (the new card appears from a spoken or typed request through Mantle, with source and timestamp) is recorded by the facilitator; automated results alone are intermediate evidence.
Known gaps (said aloud): scenarios check contract behaviour on fixtures; they do not show that a model follows instructions, that a live provider is correct, or that real traffic would allow the margin shown.

## Added in v2
S15 [core] Mantle is the centre. GIVEN the Mantle project, THEN the briefing is reached only through the skill's imported MCP tool or tools, no separate dashboard process serves a UI, and a reader can run the project's own Mantle checks offline (pack suite a6_briefing.py).
S16 [core] Surface honesty. GIVEN the cards are drawn by a thin renderer, THEN the spoken and written text never say Mantle provides widgets; it says the cards are zeocore-defined and drawn by our renderer unless a Mantle page documents native rendering.
