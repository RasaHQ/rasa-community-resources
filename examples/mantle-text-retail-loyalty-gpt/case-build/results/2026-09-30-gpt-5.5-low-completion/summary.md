# retail-loyalty-gpt-text: run summary

- Case: `retail-loyalty`; channel: rest; model: `openai/gpt-5.5-2026-04-23` (provider reported gpt-5.5-2026-04-23)
- Run: 2026-09-30T19:48:49Z to 2026-09-30T19:52:59Z
- Conversations: 8 run, 8 passed, 0 failed
- Caller turns: 31; turn latency p50 7638.0 ms, p95 11794.6 ms, max 13311.0 ms
- LLM calls: 85 (2.74 per caller turn, 12 side-channel, 0 empty completions)
- Tokens: 241357 prompt (76800 cached), 4041 completion (of which 1120 reasoning)
- Thought signatures sent back: 0 (0 LiteLLM placeholders)
- Bot text sent as 'filler' alongside a tool call: 0; change_reference: 8
- Case metric commands_sent: 8 over 9 tool results
- Server log events: willowshop.words_guard 0, mantle.turn.failed 0, mantle.orchestrator.empty_llm_response 0, mantle.memory.discovery.extractor.discover_facts.llm_error 0, mantle.tool_confirmation.declined 3, mantle.tool_confirmation.confirmed 9, mantle.tool_confirmation.recall_after_resolve_rejected 0, mantle.tool_confirmation.recall_rejected 0, mantle.skill_executor.dispatch.gated_tool.blocked 0
- Cost: 0.982415 USD; model calls priced by LiteLLM 1.101.2 bundled map

| Conversation | Kind | Result | Domain tool calls | Turn latency ms | Cost USD |
|---|---|---|---|---|---|
| adversarial-resend-after-timeout | adversarial | pass | load_member_profile→None, select_subscription_change→selected, apply_subscription_change→awaiting_confirmation, apply_subscription_change→pending/change_not_recorded, check_change_status→succeeded, route_subscription_support→routed | 9095, 9325, 8784 | 0.105762 |
| recovery-unknown-result | recovery | pass | load_member_profile→None, select_subscription_change→selected, apply_subscription_change→awaiting_confirmation, apply_subscription_change→pending/change_not_recorded, check_change_status→succeeded | 8592, 6757, 1853 | 0.073184 |
| recovery-stale-revision | recovery | pass | load_member_profile→None, select_subscription_change→selected, apply_subscription_change→awaiting_confirmation, apply_subscription_change→blocked/benefit_loss_hidden, select_subscription_change→selected, select_subscription_change→selected, apply_subscription_change→awaiting_confirmation, apply_subscription_change→succeeded | 10086, 8013, 6151, 3682, 5137 | 0.178532 |
| recovery-wrong-number | recovery | pass | load_member_profile→None, select_subscription_change→not_found/no_such_subscription, select_subscription_change→selected, apply_subscription_change→awaiting_confirmation, apply_subscription_change→succeeded | 7638, 3899, 4993, 10252 | 0.104796 |
| correction-pause-instead-at-question | correction | pass | load_member_profile→None, select_subscription_change→selected, apply_subscription_change→awaiting_confirmation, apply_subscription_change→declined, select_subscription_change→selected, apply_subscription_change→awaiting_confirmation, apply_subscription_change→succeeded | 10546, 9554, 3388, 2916 | 0.131434 |
| correction-points-loss-at-question | correction | pass | load_member_profile→None, select_subscription_change→selected, apply_subscription_change→awaiting_confirmation, apply_subscription_change→declined, select_subscription_change→selected, apply_subscription_change→awaiting_confirmation, apply_subscription_change→succeeded | 10048, 8237, 2570, 3749 | 0.122002 |
| correction-subscription-at-question | correction | pass | load_member_profile→None, select_subscription_change→selected, apply_subscription_change→awaiting_confirmation, apply_subscription_change→declined, select_subscription_change→selected, apply_subscription_change→awaiting_confirmation, apply_subscription_change→succeeded | 11795, 8953, 2312, 3229 | 0.127936 |
| correction-after-apply | correction | pass | load_member_profile→None, select_subscription_change→selected, apply_subscription_change→awaiting_confirmation, apply_subscription_change→succeeded, route_subscription_support→routed | 9555, 4144, 4882, 13311 | 0.138769 |

Synthetic scenario: Willow Shop and all its data are fictional. Pass conditions read tool calls, arguments and guard outcomes from the tracker only. Each conversation's member_intent is the change the scripted member finally wants; case-build/case_metric.py uses it to compute the case metric (renewal-stop requests executed as immediate cancellations, divided by subscription changes), and also reports dates and amounts in bot text that no tool result carried, commands sent per subscription, and receipt delivery, from the stored trackers. Conversations whose flow includes a declined confirmation or a pending result carry no no_tool_errors check, because the engine answers a second gated call in the turn that resolved the first with an error payload by design. engine_errors is empty: no in-turn rejection is known to be caused by the engine on GPT-5.5, so every failed in-turn call counts as a provider error.
