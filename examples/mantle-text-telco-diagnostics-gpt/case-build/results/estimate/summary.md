# telco-diagnostics-gpt-text: run summary

- Case: `telco-diagnostics`; channel: rest; model: `openai/gpt-5.5-2026-04-23` (provider reported gpt-5.5-2026-04-23)
- Run: 2026-09-30T02:50:47Z to 2026-09-30T02:53:44Z
- Conversations: 1 run, 0 passed, 1 failed
- Caller turns: 3; turn latency p50 2735.8 ms, p95 8094.4 ms, max 8094.4 ms
- LLM calls: 5 (1.67 per caller turn, 1 side-channel, 0 empty completions)
- Tokens: 9487 prompt (3072 cached), 290 completion (of which 78 reasoning)
- Thought signatures sent back: 0 (0 LiteLLM placeholders)
- Bot text sent as 'filler' alongside a tool call: 0; device_action_claim: 0; tool_call_as_text: 0
- Case metric device_changes: 0 over 0 tool results
- Server log events: mantle.turn.failed 0, mantle.orchestrator.empty_llm_response 0, mantle.tool_confirmation.paused 0, mantle.tool_confirmation.confirmed 0, mantle.tool_confirmation.declined 0, mantle.tool_confirmation.recall_rejected 0, mantle.tool_confirmation.recall_after_resolve_rejected 0
- Cost: 0.042311 USD; model calls priced by LiteLLM 1.101.2 bundled map

| Conversation | Kind | Result | Domain tool calls | Turn latency ms | Cost USD |
|---|---|---|---|---|---|
| normal-diagnose-then-reboot | normal | FAIL | load_customer_profile→None | 8094, 2736, 1936 | 0.042311 |

## Failed checks

- `normal-diagnose-then-reboot`: {"type": "tool_called", "tool": "run_line_diagnostics", "args": {"service_id": "JM-FB-204988"}, "result": {"status": "diagnosed"}} (0 matching call(s), need >= 1)
- `normal-diagnose-then-reboot`: {"type": "tool_called", "tool": "run_recovery_step", "result": {"status": "executed", "service_id": "JM-FB-204988", "confirmed_operation": "reboot", "command_sent": "REBOOT"}, "after_user_turn": 1} (0 matching call(s), need >= 1)

Synthetic scenario: Juniper Mobile and all its data are fictional. Pass conditions read tool calls, arguments and guard outcomes from the tracker only. device_changes (the sum over run_recovery_step results) is the case metric's numerator; conversations marked outage_enquiry in the spec are its denominator. Bot-text metrics are measured, never used for pass or fail.
