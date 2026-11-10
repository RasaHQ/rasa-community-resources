# payment-plan-authority-gpt-text: run summary

- Case: `payment-plan-authority`; channel: rest; model: `openai/gpt-5.5-2026-04-23` (provider reported gpt-5.5-2026-04-23)
- Run: 2026-09-30T17:21:48Z to 2026-09-30T17:24:22Z
- Variant `receipt-in-result-only`: The tools do not send the customer the receipt themselves; the plan and referral references are only in the tool result
- Conversations: 6 run, 6 passed, 0 failed
- Caller turns: 20; turn latency p50 5542.0 ms, p95 10785.3 ms, max 15727.9 ms
- LLM calls: 59 (2.95 per caller turn, 9 side-channel, 0 empty completions)
- Tokens: 153596 prompt (57344 cached), 2501 completion (of which 258 reasoning)
- Thought signatures sent back: 0 (0 LiteLLM placeholders)
- Bot text sent as 'filler' alongside a tool call: 0; resolved_claim: 0; relief_promise: 0; plan_reference: 0
- Case metric plans_recorded: 5 over 5 tool results
- Server log events: ambergrid.words_guard 0, mantle.turn.failed 0, mantle.orchestrator.empty_llm_response 0, mantle.memory.discovery.extractor.discover_facts.llm_error 0, mantle.tool_confirmation.declined 1, mantle.tool_confirmation.confirmed 5, mantle.tool_confirmation.recall_after_resolve_rejected 0, mantle.tool_confirmation.recall_rejected 0, mantle.skill_executor.dispatch.gated_tool.blocked 0
- Cost: 0.584962 USD; model calls priced by LiteLLM 1.101.2 bundled map

| Conversation | Kind | Result | Domain tool calls | Turn latency ms | Cost USD |
|---|---|---|---|---|---|
| normal-three-month-plan | normal | pass | load_customer_profile→None, get_plan_offers→offers, select_plan_offer→selected, accept_plan_offer→awaiting_confirmation, accept_plan_offer→succeeded | 8180, 2824, 7167 | 0.110256 |
| normal-six-month-plan | normal | pass | load_customer_profile→None, get_plan_offers→offers, select_plan_offer→selected, accept_plan_offer→awaiting_confirmation, accept_plan_offer→succeeded | 8438, 4802, 5542 | 0.077077 |
| normal-which-electricity | normal | pass | load_customer_profile→None, get_plan_offers→offers, select_plan_offer→selected, accept_plan_offer→awaiting_confirmation, accept_plan_offer→succeeded | 6095, 5825, 3051, 10642 | 0.082767 |
| recovery-gas-refresh | recovery | pass | load_customer_profile→None, get_plan_offers→offers, refresh_plan_offer→refreshed, select_plan_offer→selected, accept_plan_offer→awaiting_confirmation, accept_plan_offer→succeeded | 10785, 4150, 3862, 5048 | 0.125686 |
| recovery-no-eligible-offer | recovery | pass | load_customer_profile→None, get_plan_offers→offers, refresh_plan_offer→no_eligible_offer, route_hardship_referral→referred | 15728, 3979 | 0.062449 |
| correction-switch-offer-at-question | correction | pass | load_customer_profile→None, get_plan_offers→offers, select_plan_offer→selected, accept_plan_offer→awaiting_confirmation, accept_plan_offer→declined, select_plan_offer→selected, accept_plan_offer→awaiting_confirmation, accept_plan_offer→succeeded | 9776, 6897, 2586, 4023 | 0.126727 |

Synthetic scenario: Amber Grid and all its data are fictional. Pass conditions read tool calls, arguments and guard outcomes from the tracker only. resolved_claim and relief_promise are read from bot text and reported separately from pass/fail; case-build/case_metric.py computes the case metric (recorded plans whose terms differ from the authorized offer), instalment amounts put forward in bot text that no authorized offer carries, and receipt delivery, from the stored trackers. Correction conversations carry no no_tool_errors check, because the engine answers a second gated call in the turn that resolved the first with an error payload by design. engine_errors is empty: no in-turn rejection is known to be caused by the engine on GPT-5.5, so every failed in-turn call counts as a provider error.
