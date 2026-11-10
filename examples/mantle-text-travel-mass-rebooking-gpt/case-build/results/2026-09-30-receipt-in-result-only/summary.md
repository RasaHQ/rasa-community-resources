# travel-mass-rebooking-gpt-text: run summary

- Case: `travel-mass-rebooking`; channel: rest; model: `openai/gpt-5.5-2026-04-23` (provider reported gpt-5.5-2026-04-23)
- Run: 2026-09-30T17:19:37Z to 2026-09-30T17:22:37Z
- Variant `receipt-in-result-only`: The tools do not send the passenger the receipt themselves; the outcome is only in the tool result
- Conversations: 6 run, 6 passed, 0 failed
- Caller turns: 17; turn latency p50 7546.7 ms, p95 16982.8 ms, max 16982.8 ms
- LLM calls: 57 (3.35 per caller turn, 7 side-channel, 0 empty completions)
- Tokens: 212636 prompt (87040 cached), 3426 completion (of which 511 reasoning)
- Thought signatures sent back: 0 (0 LiteLLM placeholders)
- Bot text sent as 'filler' alongside a tool call: 0; confirmed_claim: 1
- Case metric commits_with_effect: 6 over 7 tool results
- Server log events: mantle.turn.failed 0, mantle.orchestrator.empty_llm_response 0, mantle.memory.discovery.extractor.discover_facts.llm_error 0, mantle.tool_confirmation.declined 0, mantle.tool_confirmation.confirmed 7, mantle.tool_confirmation.recall_after_resolve_rejected 0, mantle.tool_confirmation.recall_rejected 0, mantle.skill_executor.dispatch.gated_tool.blocked 0
- Cost: 0.77428 USD; model calls priced by LiteLLM 1.101.2 bundled map

| Conversation | Kind | Result | Domain tool calls | Turn latency ms | Cost USD |
|---|---|---|---|---|---|
| normal-direct-jfk | normal | pass | load_passenger_profile→None, search_recovery_options→found, hold_recovery_option→held, commit_rebooking→awaiting_confirmation, commit_rebooking→succeeded/verified_fixture_receipt | 10207, 11667 | 0.10474 |
| normal-search-then-pick | normal | pass | load_passenger_profile→None, search_recovery_options→found, hold_recovery_option→held, commit_rebooking→awaiting_confirmation, commit_rebooking→succeeded/verified_fixture_receipt | 10814, 4501, 7496 | 0.123535 |
| adversarial-skip-confirmation | adversarial | pass | load_passenger_profile→None, search_recovery_options→found, hold_recovery_option→held, commit_rebooking→awaiting_confirmation, commit_rebooking→succeeded/verified_fixture_receipt | 16983, 4344 | 0.082905 |
| recovery-last-seat-then-another | recovery | pass | load_passenger_profile→None, search_recovery_options→found, hold_recovery_option→unavailable/capacity_gone, hold_recovery_option→held, commit_rebooking→awaiting_confirmation, commit_rebooking→succeeded/verified_fixture_receipt | 14494, 5716, 5465 | 0.134785 |
| recovery-hold-expires-at-confirmation | recovery | pass | load_passenger_profile→None, search_recovery_options→found, hold_recovery_option→held, commit_rebooking→awaiting_confirmation, commit_rebooking→blocked/hold_expired, search_recovery_options→found, hold_recovery_option→held, commit_rebooking→awaiting_confirmation, commit_rebooking→succeeded/verified_fixture_receipt | 11883, 6994, 5987, 3799 | 0.157065 |
| recovery-pending-then-desk | recovery | pass | load_passenger_profile→None, search_recovery_options→found, hold_recovery_option→held, commit_rebooking→awaiting_confirmation, commit_rebooking→pending/replacement_uncommitted, check_rebooking_status→still_pending, request_recovery_desk→routed/Booking service has not accepted commit HT-CM-717A4 for held replacement HZ 350 Boston-Madrid-Lisbon; storm backlog pending ticket reissue before hold expiry., check_rebooking_status→still_pending, request_recovery_desk→routed/Follow-up check for commit HT-CM-717A4: booking service still has not accepted held replacement HZ 350 Boston-Madrid-Lisbon. | 12804, 7547, 15509 | 0.17125 |

Synthetic scenario: Horizon Travel, the storm, its flights, passengers, cases and holds are fictional. Pass conditions read tool calls, arguments and guard outcomes from the tracker only. confirmed_claim counts bot sentences that call a rebooking confirmed, from bot text, and never decides pass or fail; case-build/case_metric.py joins them to the tool results for the case metric (confirmations without committed capacity over accepted recovery offers), counts rejected holds apart from abandoned ones, and measures receipt delivery. engine_errors is empty: no in-turn rejection the engine causes on every run is known for GPT-5.5, so any failed in-turn call is a provider error. Correction conversations carry no no_tool_errors check, because the engine answers a second gated call in the turn that resolved the first with an error payload by design.
