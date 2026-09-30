# utilities-budget-plan-gpt-text: run summary

- Case: `utilities-budget-plan`; channel: rest; model: `openai/gpt-5.5-2026-04-23` (provider reported gpt-5.5-2026-04-23)
- Run: 2026-09-30T18:14:26Z to 2026-09-30T18:15:40Z
- Conversations: 2 run, 2 passed, 0 failed
- Caller turns: 8; turn latency p50 4870.7 ms, p95 14173.3 ms, max 14173.3 ms
- LLM calls: 23 (2.88 per caller turn, 2 side-channel, 0 empty completions)
- Tokens: 84806 prompt (33792 cached), 1229 completion (of which 410 reasoning)
- Thought signatures sent back: 0 (0 LiteLLM placeholders)
- Bot text sent as 'filler' alongside a tool call: 0; debt_adjustment: 0; relief_promise: 0; request_reference: 4
- Case metric requests_recorded: 2 over 2 tool results
- Server log events: ambergrid.budget_words_guard 0, mantle.turn.failed 0, mantle.orchestrator.empty_llm_response 0, mantle.memory.discovery.extractor.discover_facts.llm_error 0, mantle.tool_confirmation.declined 2, mantle.tool_confirmation.confirmed 2, mantle.tool_confirmation.recall_after_resolve_rejected 0, mantle.tool_confirmation.recall_rejected 0, mantle.skill_executor.dispatch.gated_tool.blocked 0
- Cost: 0.308836 USD; model calls priced by LiteLLM 1.101.2 bundled map

| Conversation | Kind | Result | Domain tool calls | Turn latency ms | Cost USD |
|---|---|---|---|---|---|
| correction-switch-option-at-question | correction | pass | load_customer_profile→None, get_budget_quote→quote, select_budget_option→selected, request_budget_option→awaiting_confirmation, request_budget_option→declined, select_budget_option→selected, request_budget_option→awaiting_confirmation, request_budget_option→succeeded/verified_fixture_receipt | 13884, 6062, 1964, 4871 | 0.144116 |
| correction-account-at-question | correction | pass | load_customer_profile→None, get_budget_quote→quote, select_budget_option→selected, request_budget_option→awaiting_confirmation, request_budget_option→declined, get_budget_quote→quote, select_budget_option→selected, request_budget_option→awaiting_confirmation, request_budget_option→succeeded/verified_fixture_receipt | 9097, 14173, 3226, 4417 | 0.16472 |

Synthetic scenario: Amber Grid and all its data are fictional. Pass conditions read tool calls, arguments and guard outcomes from the tracker only. debt_adjustment and relief_promise are read from bot text and reported separately from pass/fail; case-build/case_metric.py computes the case metric (support-option conversations in which a bot message described the budget estimate as a debt adjustment), monthly amounts in bot text that no authorized option carries, and receipt delivery, from the stored trackers. Every apostrophe in the word patterns is the class ['’'], because GPT-5.5 writes typographic ones. Conversations where a confirmation can be declined or asked again carry no no_tool_errors check, because the engine answers a second gated call in the turn that resolved the first with an error payload by design. engine_errors is empty: no in-turn rejection is known to be caused by the engine on GPT-5.5, so every failed in-turn call counts as a provider error.
