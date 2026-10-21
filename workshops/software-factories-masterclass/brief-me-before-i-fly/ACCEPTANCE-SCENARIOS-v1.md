# Acceptance scenarios v1 for "Brief me before I fly" (owner: rasa-ops; kept apart from the implementation)
sow: software-factories-masterclass-SOW-02
Locked with SPEC-brief-me-before-i-fly-v1.md. Each scenario is stated against the public contract only (MCP tools, widget.upsert events, data_ref); none reads implementation internals.
Tag: [core] act 1, [m] act 2 market, [manual] rehearsal check, not automatable offline. All automatable scenarios run on labelled replay fixtures; live mode is a separate dated check, never a substitute.

## Core (act 1)
S1 [core] Fast start. GIVEN a conversation, WHEN start_briefing is called, THEN it returns a job_id and status "started" before any widget data exists, and get_briefing reports progress entries in order (flight, weather, timeline).
S2 [core] One card per widget_id. GIVEN a widget.upsert for widget_id W at revision 2, WHEN another for W arrives at revision 3, THEN the dashboard holds one card for W showing revision 3; a later event at revision 2 or lower is ignored.
S3 [core] Provenance on screen. GIVEN any rendered card, THEN it shows source, as_of and fetched_at from its data_ref, and every number, time and label on the card equals the payload value (no value typed by the model).
S4 [core] Partial failure. GIVEN the flight adapter fails, WHEN weather succeeds, THEN the weather card renders, the flight card shows "unavailable" with the reason, and no earlier flight value is shown as current.
S5 [core] Destination change race. GIVEN a weather request for city A is running, WHEN revise_briefing changes the destination to city B and A's result arrives afterwards, THEN A's result is discarded and the weather card for B is unchanged.
S6 [core] Replay is labelled. GIVEN any data_ref with replay=true, THEN the card shows a visible replay label and the spoken answer says the data is replayed.
S7 [core] Transfer time is an assumption. GIVEN the user asks whether the updated arrival leaves time for a 17:00 meeting, THEN the arrival_timeline shows transfer_minutes labelled "assumption", margin_minutes is computed from payload values, and neither the card nor the speech says traffic or live.
S8 [core] Missing input is asked, not guessed. GIVEN the meeting time or transfer assumption is missing, WHEN get_briefing runs, THEN status is needs_input with the field and question; Mantle asks it; the job resumes when answered.
S9 [core] Status words are the provider's. GIVEN a flight data_ref, THEN the reported status shown or spoken equals reported_status; "delayed" appears only if that string says so; scheduled and estimated times are shown separately.
S10 [core] Session ownership. GIVEN a job created in conversation X, WHEN get_briefing or revise_briefing is called from conversation Y with that job_id, THEN it is refused and nothing changes in X.
S11 [core] Completion is inspected. GIVEN the OpenAI session stream ends without a saved outcome or with a failed tool result, THEN get_briefing returns incomplete or failed, never complete.
S12 [core] No secrets. GIVEN the repository, fixtures, logs and recorded outputs, THEN none contains an API key or token pattern.
S13 [manual] Voice and screen share one session. GIVEN a spoken weather request in the browser, THEN the matching card appears for that session only. This is the main integration risk; rehearse it, state the evidence level aloud.
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
