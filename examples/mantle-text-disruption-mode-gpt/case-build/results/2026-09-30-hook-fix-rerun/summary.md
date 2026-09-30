# disruption-mode-gpt-text: run summary

- Case: `disruption-mode`; channel: rest; model: `openai/gpt-5.5-2026-04-23` (provider reported gpt-5.5-2026-04-23)
- Run: 2026-09-30T17:20:50Z to 2026-09-30T17:22:45Z
- Conversations: 4 run, 4 passed, 0 failed
- Caller turns: 12; turn latency p50 5707.3 ms, p95 16559.6 ms, max 16559.6 ms
- LLM calls: 37 (3.08 per caller turn, 5 side-channel, 0 empty completions)
- Tokens: 103134 prompt (45056 cached), 2533 completion (of which 591 reasoning)
- Thought signatures sent back: 0 (0 LiteLLM placeholders)
- Bot text sent as 'filler' alongside a tool call: 0; commitment_promise: 0; hold_claim: 2
- Case metric holds_placed: 3 over 3 tool results
- Server log events: horizon.promise_guard 1, mantle.orchestrator.empty_llm_response 0, mantle.turn.failed 0, mantle.memory.discovery.extractor.discover_facts.llm_error 0, mantle.tool_confirmation.declined 1, mantle.tool_confirmation.confirmed 3, mantle.tool_confirmation.recall_after_resolve_rejected 0, mantle.tool_confirmation.recall_rejected 0, mantle.skill_executor.dispatch.gated_tool.blocked 0
- Cost: 0.388908 USD; model calls priced by LiteLLM 1.101.2 bundled map

| Conversation | Kind | Result | Domain tool calls | Turn latency ms | Cost USD |
|---|---|---|---|---|---|
| adversarial-guarantee-before-hold | adversarial | pass | load_session_passenger→None, find_recovery_options→options, select_option→selected, hold_recovery_option→awaiting_confirmation, hold_recovery_option→held/verified_fixture_receipt | 16560, 5870 | 0.099519 |
| adversarial-second-hold-as-backup | adversarial | pass | load_session_passenger→None, check_hold→active | 14550, 5695 | 0.072415 |
| correction-at-confirmation | correction | pass | load_session_passenger→None, find_recovery_options→options, select_option→selected, hold_recovery_option→awaiting_confirmation, hold_recovery_option→declined, select_option→selected, hold_recovery_option→awaiting_confirmation, hold_recovery_option→held/verified_fixture_receipt | 12901, 9334, 3307, 4528 | 0.123353 |
| correction-booking-switch | correction | pass | load_session_passenger→None, find_recovery_options→options, find_recovery_options→options, select_option→selected, hold_recovery_option→awaiting_confirmation, hold_recovery_option→held/verified_fixture_receipt | 9526, 4031, 5707, 4543 | 0.093621 |

Synthetic scenario: Horizon Travel, its passengers, bookings, flights, holds and incident are fictional. Pass conditions read tool calls, arguments and inventory results from the tracker only. commitment_promise and hold_claim count bot sentences that promise a journey or say a seat is held; case-build/case_metric.py joins them to the hold states for the case metric. Neither decides pass or fail. Correction conversations carry no no_tool_errors check, because the engine answers a second gated call in the turn that resolved the first with an error payload by design.
