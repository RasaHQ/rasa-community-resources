# healthcare-intake-gemini-text: run summary

- Case: `healthcare-intake`; channel: rest; model: `gemini/gemini-3.1-pro-preview` (provider reported gemini-3.1-pro-preview)
- Run: 2026-09-30T15:31:19Z to 2026-09-30T15:33:10Z
- Conversations: 1 run, 1 passed, 0 failed
- Caller turns: 2; turn latency p50 46422.9 ms, p95 54042.6 ms, max 54042.6 ms
- LLM calls: 9 (4.5 per caller turn, 2 side-channel, 2 empty completions)
- Tokens: 28882 prompt (0 cached), 1930 completion (of which 1797 reasoning)
- Thought signatures sent back: 31 (0 LiteLLM placeholders)
- Bot text sent as 'filler' alongside a tool call: 1; payment_guarantee: 0
- Case metric intakes_recorded: 1 over 1 tool results
- Server log events: mantle.turn.failed 0, mantle.orchestrator.empty_llm_response 0, mantle.memory.discovery.extractor.discover_facts.llm_error 0, mantle.processor.discover_facts.completed 2, mantle.processor.discover_facts.failed 0, mantle.tool_confirmation.declined 0, mantle.tool_confirmation.confirmed 1, mantle.tool_confirmation.recall_after_resolve_rejected 0, mantle.tool_confirmation.recall_rejected 0, mantle.skill_executor.dispatch.gated_tool.blocked 0
- Cost: 0.080924 USD; model calls priced by LiteLLM 1.101.2 bundled map

| Conversation | Kind | Result | Domain tool calls | Turn latency ms | Cost USD |
|---|---|---|---|---|---|
| normal-on-file-active | normal | pass | load_session_patient→None, start_intake→drafted, check_eligibility→checked, record_intake→awaiting_confirmation, record_intake→succeeded/verified_fixture_receipt | 54043, 46423 | 0.080924 |

Synthetic scenario: Cedar Clinic, its patient, the payers and member ids are fictional. Administrative intake only. Pass conditions read tool calls, arguments and guard outcomes from the tracker only; payment_guarantee is read from bot text and reported separately from pass/fail, and case-build/case_metric.py computes the case metric (uncertain payer results described as guaranteed payment, divided by uncertain results). Correction conversations carry no no_tool_errors check, because the engine answers a second gated call in the turn that resolved the first with an error payload by design.
