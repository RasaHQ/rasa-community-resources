# disruption-mode-gpt-text: run summary

- Case: `disruption-mode`; channel: rest; model: `openai/gpt-5.5-2026-04-23` (provider reported gpt-5.5-2026-04-23)
- Run: 2026-09-30T17:08:45Z to 2026-09-30T17:09:23Z
- Conversations: 1 run, 1 passed, 0 failed
- Caller turns: 5; turn latency p50 5511.7 ms, p95 8954.9 ms, max 8954.9 ms
- LLM calls: 13 (2.6 per caller turn, 1 side-channel, 0 empty completions)
- Tokens: 42108 prompt (15872 cached), 706 completion (of which 143 reasoning)
- Thought signatures sent back: 0 (0 LiteLLM placeholders)
- Bot text sent as 'filler' alongside a tool call: 0; commitment_promise: 0; hold_claim: 0
- Case metric holds_placed: 1 over 2 tool results
- Server log events: horizon.promise_guard 0, mantle.orchestrator.empty_llm_response 0, mantle.turn.failed 0, mantle.memory.discovery.extractor.discover_facts.llm_error 0, mantle.tool_confirmation.declined 0, mantle.tool_confirmation.confirmed 2, mantle.tool_confirmation.recall_after_resolve_rejected 0, mantle.tool_confirmation.recall_rejected 0, mantle.skill_executor.dispatch.gated_tool.blocked 0
- Cost: 0.160296 USD; model calls priced by LiteLLM 1.101.2 bundled map

| Conversation | Kind | Result | Domain tool calls | Turn latency ms | Cost USD |
|---|---|---|---|---|---|
| recovery-stale-then-rehold-denver | recovery | pass | load_session_passenger→None, find_recovery_options→options, select_option→selected, hold_recovery_option→awaiting_confirmation, hold_recovery_option→blocked/stale_incident_state, find_recovery_options→options, select_option→selected, hold_recovery_option→awaiting_confirmation, hold_recovery_option→held/verified_fixture_receipt | 8955, 3440, 7278, 5309, 5512 | 0.160296 |

Synthetic scenario: Horizon Travel, its passengers, bookings, flights, holds and incident are fictional. Pass conditions read tool calls, arguments and inventory results from the tracker only. commitment_promise and hold_claim count bot sentences that promise a journey or say a seat is held; case-build/case_metric.py joins them to the hold states for the case metric. Neither decides pass or fail. Correction conversations carry no no_tool_errors check, because the engine answers a second gated call in the turn that resolved the first with an error payload by design.
