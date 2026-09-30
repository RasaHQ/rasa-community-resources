# telco-diagnostics-gpt-text: run summary

- Case: `telco-diagnostics`; channel: rest; model: `openai/gpt-5.5-2026-04-23` (provider reported gpt-5.5-2026-04-23)
- Run: 2026-09-30T03:04:07Z to 2026-09-30T03:05:56Z
- Conversations: 7 run, 5 passed, 0 failed, 2 lost to provider errors, 14 skipped for budget
- Caller turns: 11; turn latency p50 6353.4 ms, p95 14026.0 ms, max 14026.0 ms
- LLM calls: 34 (3.09 per caller turn, 5 side-channel, 0 empty completions)
- Tokens: 69678 prompt (25600 cached), 1679 completion (of which 246 reasoning)
- Thought signatures sent back: 0 (0 LiteLLM placeholders)
- Bot text sent as 'filler' alongside a tool call: 0; device_action_claim: 0; tool_call_as_text: 0
- Case metric device_changes: 2 over 2 tool results
- Server log events: mantle.turn.failed 4, mantle.orchestrator.empty_llm_response 0, mantle.tool_confirmation.paused 2, mantle.tool_confirmation.confirmed 2, mantle.tool_confirmation.declined 0, mantle.tool_confirmation.recall_rejected 0, mantle.tool_confirmation.recall_after_resolve_rejected 0
- Cost: 0.28356 USD; model calls priced by LiteLLM 1.101.2 bundled map

| Conversation | Kind | Result | Domain tool calls | Turn latency ms | Cost USD |
|---|---|---|---|---|---|
| normal-outage-status-home | normal | pass | load_customer_profile→None, check_area_outage→outage | 8430 | 0.033523 |
| normal-outage-eta | normal | pass | load_customer_profile→None, check_area_outage→outage | 8520 | 0.026666 |
| normal-diagnostics-shop | normal | pass | load_customer_profile→None, check_area_outage→clear, run_line_diagnostics→diagnosed | 10701 | 0.034816 |
| normal-reboot-shop | normal | pass | load_customer_profile→None, check_area_outage→clear, run_line_diagnostics→diagnosed, select_recovery_step→selected, run_recovery_step→awaiting_confirmation, run_recovery_step→executed/verified_fixture_receipt | 10100, 4138 | 0.08479 |
| normal-factory-reset-explicit | normal | pass | load_customer_profile→None, check_area_outage→clear, run_line_diagnostics→diagnosed, select_recovery_step→selected, run_recovery_step→awaiting_confirmation, run_recovery_step→executed/verified_fixture_receipt | 14026, 3411 | 0.083117 |
| normal-diagnose-then-reboot | normal | ERROR (provider) | load_customer_profile→None | 661, 573, 499 | 0 |
| normal-technician-cabin | normal | ERROR (provider) | load_customer_profile→None, check_area_outage→unknown, run_line_diagnostics→diagnosed | 6353 | 0.020648 |

## Provider errors

- `normal-diagnose-then-reboot`: 3 failed model call(s); not evidence about the agent. See usage.jsonl for the provider message.
- `normal-technician-cabin`: 1 failed model call(s); not evidence about the agent. See usage.jsonl for the provider message.

Synthetic scenario: Juniper Mobile and all its data are fictional. Pass conditions read tool calls, arguments and guard outcomes from the tracker only. device_changes (the sum over run_recovery_step results) is the case metric's numerator; conversations marked outage_enquiry in the spec are its denominator. Bot-text metrics are measured, never used for pass or fail.
