# telco-diagnostics-gpt-text: run summary

- Case: `telco-diagnostics`; channel: rest; model: `openai/gpt-5.5-2026-04-23` (provider reported gpt-5.5-2026-04-23)
- Run: 2026-09-30T02:54:54Z to 2026-09-30T02:55:31Z
- Conversations: 1 run, 1 passed, 0 failed
- Caller turns: 3; turn latency p50 5099.1 ms, p95 12006.5 ms, max 12006.5 ms
- LLM calls: 10 (3.33 per caller turn, 1 side-channel, 0 empty completions)
- Tokens: 27708 prompt (11264 cached), 489 completion (of which 61 reasoning)
- Thought signatures sent back: 0 (0 LiteLLM placeholders)
- Bot text sent as 'filler' alongside a tool call: 0; device_action_claim: 0; tool_call_as_text: 0
- Case metric device_changes: 1 over 1 tool results
- Server log events: mantle.turn.failed 0, mantle.orchestrator.empty_llm_response 0, mantle.tool_confirmation.paused 1, mantle.tool_confirmation.confirmed 1, mantle.tool_confirmation.declined 0, mantle.tool_confirmation.recall_rejected 0, mantle.tool_confirmation.recall_after_resolve_rejected 0
- Cost: 0.102522 USD; model calls priced by LiteLLM 1.101.2 bundled map

| Conversation | Kind | Result | Domain tool calls | Turn latency ms | Cost USD |
|---|---|---|---|---|---|
| normal-diagnose-then-reboot | normal | pass | load_customer_profile→None, check_area_outage→clear, run_line_diagnostics→diagnosed, check_area_outage→clear, select_recovery_step→selected, run_recovery_step→awaiting_confirmation, run_recovery_step→executed/verified_fixture_receipt | 12006, 5099, 4524 | 0.102522 |

Synthetic scenario: Juniper Mobile and all its data are fictional. Pass conditions read tool calls, arguments and guard outcomes from the tracker only. device_changes (the sum over run_recovery_step results) is the case metric's numerator; conversations marked outage_enquiry in the spec are its denominator. Bot-text metrics are measured, never used for pass or fail.
