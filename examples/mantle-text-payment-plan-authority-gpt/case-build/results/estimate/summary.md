# payment-plan-authority-gpt-text: run summary

- Case: `payment-plan-authority`; channel: rest; model: `openai/gpt-5.5-2026-04-23` (provider reported gpt-5.5-2026-04-23)
- Run: 2026-09-30T17:09:58Z to 2026-09-30T17:10:30Z
- Conversations: 1 run, 1 passed, 0 failed
- Caller turns: 4; turn latency p50 5614.0 ms, p95 7700.5 ms, max 7700.5 ms
- LLM calls: 11 (2.75 per caller turn, 2 side-channel, 0 empty completions)
- Tokens: 28384 prompt (9216 cached), 529 completion (of which 61 reasoning)
- Thought signatures sent back: 0 (0 LiteLLM placeholders)
- Bot text sent as 'filler' alongside a tool call: 0; resolved_claim: 0; relief_promise: 0; plan_reference: 2
- Case metric plans_recorded: 1 over 1 tool results
- Server log events: ambergrid.words_guard 0, mantle.turn.failed 0, mantle.orchestrator.empty_llm_response 0, mantle.memory.discovery.extractor.discover_facts.llm_error 0, mantle.tool_confirmation.declined 0, mantle.tool_confirmation.confirmed 1, mantle.tool_confirmation.recall_after_resolve_rejected 0, mantle.tool_confirmation.recall_rejected 0, mantle.skill_executor.dispatch.gated_tool.blocked 0
- Cost: 0.116318 USD; model calls priced by LiteLLM 1.101.2 bundled map

| Conversation | Kind | Result | Domain tool calls | Turn latency ms | Cost USD |
|---|---|---|---|---|---|
| correction-switch-offer-at-question | correction | pass | load_customer_profile→None, get_plan_offers→offers, select_plan_offer→selected, accept_plan_offer→awaiting_confirmation, accept_plan_offer→succeeded | 7700, 5614, 3513, 7193 | 0.116318 |

Synthetic scenario: Amber Grid and all its data are fictional. Pass conditions read tool calls, arguments and guard outcomes from the tracker only. resolved_claim and relief_promise are read from bot text and reported separately from pass/fail; case-build/case_metric.py computes the case metric (recorded plans whose terms differ from the authorized offer), instalment amounts put forward in bot text that no authorized offer carries, and receipt delivery, from the stored trackers. Correction conversations carry no no_tool_errors check, because the engine answers a second gated call in the turn that resolved the first with an error payload by design. engine_errors is empty: no in-turn rejection is known to be caused by the engine on GPT-5.5, so every failed in-turn call counts as a provider error.
