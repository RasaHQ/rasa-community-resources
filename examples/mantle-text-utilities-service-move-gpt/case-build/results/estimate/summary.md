# utilities-service-move-gpt-text: run summary

- Case: `utilities-service-move`; channel: rest; model: `openai/gpt-5.5-2026-04-23` (provider reported gpt-5.5-2026-04-23)
- Run: 2026-09-30T18:05:00Z to 2026-09-30T18:05:49Z
- Conversations: 1 run, 1 passed, 0 failed
- Caller turns: 5; turn latency p50 6462.8 ms, p95 10760.9 ms, max 10760.9 ms
- LLM calls: 14 (2.8 per caller turn, 2 side-channel, 0 empty completions)
- Tokens: 49345 prompt (18432 cached), 735 completion (of which 170 reasoning)
- Thought signatures sent back: 0 (0 LiteLLM placeholders)
- Bot text sent as 'filler' alongside a tool call: 0; closure_claim: 0; move_reference: 4
- Case metric move_orders_recorded: 2 over 2 tool results
- Server log events: ambergrid.closure_words_guard 0, mantle.turn.failed 0, mantle.orchestrator.empty_llm_response 0, mantle.memory.discovery.extractor.discover_facts.llm_error 0, mantle.tool_confirmation.declined 0, mantle.tool_confirmation.confirmed 2, mantle.tool_confirmation.recall_after_resolve_rejected 0, mantle.tool_confirmation.recall_rejected 0, mantle.skill_executor.dispatch.gated_tool.blocked 0
- Cost: 0.185831 USD; model calls priced by LiteLLM 1.101.2 bundled map

| Conversation | Kind | Result | Domain tool calls | Turn latency ms | Cost USD |
|---|---|---|---|---|---|
| correction-after-order | correction | pass | load_customer_profile→None, start_move_draft→drafted, submit_move_order→awaiting_confirmation, submit_move_order→succeeded, update_move_draft→drafted, submit_move_order→awaiting_confirmation, submit_move_order→succeeded | 10761, 5014, 8138, 5239, 6463 | 0.185831 |

Synthetic scenario: Amber Grid and all its data are fictional. Pass conditions read tool calls, arguments and results from the tracker only. closure_claim is read from bot text (straight and typographic apostrophes) and reported separately from pass/fail; case-build/case_metric.py computes the case metric (moves whose current service was reported off, or ending before the confirmed move-out day, over move requests) and receipt delivery from the stored trackers. Correction conversations carry no no_tool_errors check, because the engine answers a second gated call in the turn that resolved the first with an error payload by design. engine_errors is empty: no in-turn rejection is known to be caused by the engine on GPT-5.5, so every failed in-turn call counts as a provider error.
