# healthcare-intake-gemini-text: run summary

- Case: `healthcare-intake`; channel: rest; model: `gemini/gemini-3.1-pro-preview` (provider reported gemini-3.1-pro-preview)
- Run: 2026-09-30T15:30:07Z to 2026-09-30T15:30:52Z
- Conversations: 1 run, 0 passed, 1 failed
- Caller turns: 2; turn latency p50 4605.9 ms, p95 28522.8 ms, max 28522.8 ms
- LLM calls: 8 (4.0 per caller turn, 1 side-channel, 1 empty completions)
- Tokens: 30067 prompt (0 cached), 1593 completion (of which 1314 reasoning)
- Thought signatures sent back: 25 (0 LiteLLM placeholders)
- Bot text sent as 'filler' alongside a tool call: 0; payment_guarantee: 0
- Case metric intakes_recorded: 0 over 0 tool results
- Server log events: mantle.turn.failed 0, mantle.orchestrator.empty_llm_response 0, mantle.memory.discovery.extractor.discover_facts.llm_error 0, mantle.processor.discover_facts.completed 1, mantle.processor.discover_facts.failed 0, mantle.tool_confirmation.declined 0, mantle.tool_confirmation.confirmed 0, mantle.tool_confirmation.recall_after_resolve_rejected 0, mantle.tool_confirmation.recall_rejected 0, mantle.skill_executor.dispatch.gated_tool.blocked 0
- Cost: 0.07925 USD; model calls priced by LiteLLM 1.101.2 bundled map

| Conversation | Kind | Result | Domain tool calls | Turn latency ms | Cost USD |
|---|---|---|---|---|---|
| normal-new-insurance-unavailable | normal | FAIL | load_session_patient→None, start_intake→drafted, update_intake→updated, check_eligibility→checked, assign_access_followup→assigned, record_intake→awaiting_confirmation | 28523, 4606 | 0.07925 |

## Failed checks

- `normal-new-insurance-unavailable`: {"type": "tool_called", "tool": "record_intake", "result": {"status": "succeeded", "payer_response": {"code": "EL-42"}, "payment_guarantee": null, "open_question_owner": {"owner": "patient access owner"}, "member_id": "OMH-55812040"}} (0 matching call(s), need >= 1)
- `normal-new-insurance-unavailable`: {"type": "tool_order", "steps": [{"tool": "check_eligibility", "result": {"payer_response": {"code": "EL-42"}}}, {"tool": "assign_access_followup", "result": {"status": "assigned"}}, {"tool": "record_intake", "result": {"status": "succeeded"}}]} (no record_intake call after position 5)

Synthetic scenario: Cedar Clinic, its patient, the payers and member ids are fictional. Administrative intake only. Pass conditions read tool calls, arguments and guard outcomes from the tracker only; payment_guarantee is read from bot text and reported separately from pass/fail, and case-build/case_metric.py computes the case metric (uncertain payer results described as guaranteed payment, divided by uncertain results). Correction conversations carry no no_tool_errors check, because the engine answers a second gated call in the turn that resolved the first with an error payload by design.
