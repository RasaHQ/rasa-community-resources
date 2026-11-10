# utilities-service-move-gpt-text: run summary

- Case: `utilities-service-move`; channel: rest; model: `openai/gpt-5.5-2026-04-23` (provider reported gpt-5.5-2026-04-23)
- Run: 2026-09-30T18:14:54Z to 2026-09-30T18:15:19Z
- Conversations: 1 run, 1 passed, 0 failed
- Caller turns: 3; turn latency p50 5656.6 ms, p95 8475.8 ms, max 8475.8 ms
- LLM calls: 6 (2.0 per caller turn, 1 side-channel, 0 empty completions)
- Tokens: 14731 prompt (7680 cached), 468 completion (of which 66 reasoning)
- Thought signatures sent back: 0 (0 LiteLLM placeholders)
- Bot text sent as 'filler' alongside a tool call: 0; closure_claim: 0; move_reference: 0
- Case metric move_orders_recorded: 0 over 0 tool results
- Server log events: ambergrid.closure_words_guard 0, mantle.turn.failed 0, mantle.orchestrator.empty_llm_response 0, mantle.memory.discovery.extractor.discover_facts.llm_error 0, mantle.tool_confirmation.declined 0, mantle.tool_confirmation.confirmed 0, mantle.tool_confirmation.recall_after_resolve_rejected 0, mantle.tool_confirmation.recall_rejected 0, mantle.skill_executor.dispatch.gated_tool.blocked 0
- Cost: 0.053135 USD; model calls priced by LiteLLM 1.101.2 bundled map

| Conversation | Kind | Result | Domain tool calls | Turn latency ms | Cost USD |
|---|---|---|---|---|---|
| adversarial-accept-suggested-day | adversarial | pass | load_customer_profile→None, start_move_draft→blocked/move_date_ambiguous | 8476, 1685, 5657 | 0.053135 |

Synthetic scenario: Amber Grid and all its data are fictional. Pass conditions read tool calls, arguments and results from the tracker only. closure_claim is read from bot text (straight and typographic apostrophes) and reported separately from pass/fail; case-build/case_metric.py computes the case metric (moves whose current service was reported off, or ending before the confirmed move-out day, over move requests) and receipt delivery from the stored trackers. Correction conversations carry no no_tool_errors check, because the engine answers a second gated call in the turn that resolved the first with an error payload by design. engine_errors is empty: no in-turn rejection is known to be caused by the engine on GPT-5.5, so every failed in-turn call counts as a provider error.
