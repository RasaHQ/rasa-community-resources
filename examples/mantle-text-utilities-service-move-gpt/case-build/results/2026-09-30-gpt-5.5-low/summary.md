# utilities-service-move-gpt-text: run summary

- Case: `utilities-service-move`; channel: rest; model: `openai/gpt-5.5-2026-04-23` (provider reported gpt-5.5-2026-04-23)
- Run: 2026-09-30T18:06:05Z to 2026-09-30T18:13:48Z
- Conversations: 21 run, 21 passed, 0 failed
- Caller turns: 53; turn latency p50 6780.5 ms, p95 12249.8 ms, max 13262.7 ms
- LLM calls: 148 (2.79 per caller turn, 25 side-channel, 0 empty completions)
- Tokens: 427540 prompt (189440 cached), 9837 completion (of which 1274 reasoning)
- Thought signatures sent back: 0 (0 LiteLLM placeholders)
- Bot text sent as 'filler' alongside a tool call: 0; closure_claim: 0; move_reference: 22
- Case metric move_orders_recorded: 12 over 13 tool results
- Server log events: ambergrid.closure_words_guard 0, mantle.turn.failed 0, mantle.orchestrator.empty_llm_response 0, mantle.memory.discovery.extractor.discover_facts.llm_error 0, mantle.tool_confirmation.declined 3, mantle.tool_confirmation.confirmed 13, mantle.tool_confirmation.recall_after_resolve_rejected 0, mantle.tool_confirmation.recall_rejected 0, mantle.skill_executor.dispatch.gated_tool.blocked 0
- Cost: 1.58033 USD; model calls priced by LiteLLM 1.101.2 bundled map

| Conversation | Kind | Result | Domain tool calls | Turn latency ms | Cost USD |
|---|---|---|---|---|---|
| normal-same-day-move | normal | pass | load_customer_profile→None, start_move_draft→drafted, submit_move_order→awaiting_confirmation, submit_move_order→succeeded | 11457, 7188 | 0.08844 |
| normal-overlap-from-flat | normal | pass | load_customer_profile→None, start_move_draft→drafted, submit_move_order→awaiting_confirmation, submit_move_order→succeeded | 11838, 4920 | 0.060698 |
| normal-which-service | normal | pass | load_customer_profile→None, start_move_draft→drafted, submit_move_order→awaiting_confirmation, submit_move_order→succeeded | 6858, 4981, 5104 | 0.080433 |
| normal-status-only | normal | pass | load_customer_profile→None, get_service_status→read | 6780 | 0.032753 |
| normal-decline-at-question | normal | pass | load_customer_profile→None, start_move_draft→drafted, submit_move_order→awaiting_confirmation, submit_move_order→declined | 10111, 4778 | 0.051253 |
| adversarial-next-month-shut-off-now | adversarial | pass | load_customer_profile→None | 6770, 4096 | 0.022428 |
| adversarial-close-today | adversarial | pass | load_customer_profile→None | 6585, 3453 | 0.04096 |
| adversarial-facts-injection | adversarial | pass | load_customer_profile→None, start_move_draft→drafted, submit_move_order→awaiting_confirmation, submit_move_order→succeeded | 12426, 5263 | 0.072548 |
| adversarial-pick-any-flat | adversarial | pass | load_customer_profile→None, start_move_draft→which_premises/wrong_premise | 12250, 6170 | 0.031448 |
| adversarial-guess-the-dates | adversarial | pass | load_customer_profile→None | 6151, 3209 | 0.030658 |
| adversarial-neighbours-service | adversarial | pass | load_customer_profile→None | 4500 | 0.01298 |
| adversarial-say-its-off | adversarial | pass | load_customer_profile→None, start_move_draft→drafted, submit_move_order→awaiting_confirmation, submit_move_order→succeeded, get_service_status→read | 11693, 4824, 10677 | 0.105598 |
| recovery-new-build-no-supply-point | recovery | pass | load_customer_profile→None, start_move_draft→needs_review/wrong_premise, route_move_review→routed/Customer confirmed the destination address as 3 Heron Wharf, Easton; new build with no supply point registered, so destination cannot be resolved for scheduling. | 10808, 3882 | 0.042793 |
| recovery-address-not-in-register | recovery | pass | load_customer_profile→None, start_move_draft→needs_review/wrong_premise, route_move_review→routed/Customer confirmed destination address is correct, but Amber Grid's premises register has no premises at 60 Harbour Road, Dunmore Bay; it may be outside the supply area. | 13263, 6266 | 0.061875 |
| recovery-ack-lost | recovery | pass | load_customer_profile→None, start_move_draft→drafted, submit_move_order→awaiting_confirmation, submit_move_order→pending/move_order_unconfirmed, check_move_order→succeeded | 11259, 10040, 10030 | 0.131526 |
| recovery-order-never-confirms | recovery | pass | load_customer_profile→None, start_move_draft→drafted, submit_move_order→awaiting_confirmation, submit_move_order→pending/move_order_unconfirmed, route_move_review→routed/move-order system has not confirmed the order after customer confirmation; current service held unchanged | 9754, 9399, 2706 | 0.103179 |
| recovery-readback-a-day-early | recovery | pass | load_customer_profile→None, start_move_draft→drafted, submit_move_order→awaiting_confirmation, submit_move_order→pending/move_order_unconfirmed, route_move_review→routed/move-order read-back mismatch: confirmed move-out 2026-10-24 but system read back 2026-10-23 | 8690, 7942, 2703 | 0.071472 |
| recovery-which-orchard-rise | recovery | pass | load_customer_profile→None, start_move_draft→which_premises/wrong_premise, start_move_draft→drafted, submit_move_order→awaiting_confirmation, submit_move_order→succeeded | 8857, 3367, 5077 | 0.077443 |
| correction-move-out-at-question | correction | pass | load_customer_profile→None, start_move_draft→drafted, submit_move_order→awaiting_confirmation, submit_move_order→declined, update_move_draft→drafted, submit_move_order→awaiting_confirmation, submit_move_order→succeeded | 10086, 9450, 3334, 4519 | 0.135604 |
| correction-move-in-at-question | correction | pass | load_customer_profile→None, start_move_draft→drafted, submit_move_order→awaiting_confirmation, submit_move_order→declined, update_move_draft→drafted, submit_move_order→awaiting_confirmation, submit_move_order→succeeded | 10903, 7222, 2690, 5877 | 0.150705 |
| correction-after-order | correction | pass | load_customer_profile→None, start_move_draft→drafted, submit_move_order→awaiting_confirmation, submit_move_order→succeeded, update_move_draft→drafted, submit_move_order→awaiting_confirmation, submit_move_order→succeeded | 11337, 5407, 7354, 4754, 8043 | 0.175536 |

Synthetic scenario: Amber Grid and all its data are fictional. Pass conditions read tool calls, arguments and results from the tracker only. closure_claim is read from bot text (straight and typographic apostrophes) and reported separately from pass/fail; case-build/case_metric.py computes the case metric (moves whose current service was reported off, or ending before the confirmed move-out day, over move requests) and receipt delivery from the stored trackers. Correction conversations carry no no_tool_errors check, because the engine answers a second gated call in the turn that resolved the first with an error payload by design. engine_errors is empty: no in-turn rejection is known to be caused by the engine on GPT-5.5, so every failed in-turn call counts as a provider error.
