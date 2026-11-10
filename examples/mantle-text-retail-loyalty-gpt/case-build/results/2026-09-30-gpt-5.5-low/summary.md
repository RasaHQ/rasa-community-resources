# retail-loyalty-gpt-text: run summary

- Case: `retail-loyalty`; channel: rest; model: `openai/gpt-5.5-2026-04-23` (provider reported gpt-5.5-2026-04-23)
- Run: 2026-09-30T19:15:30Z to 2026-09-30T19:20:08Z
- Conversations: 14 run, 12 passed, 0 failed, 2 lost to provider errors, 6 skipped for budget
- Caller turns: 38; turn latency p50 5309.0 ms, p95 13883.5 ms, max 14186.8 ms
- LLM calls: 103 (2.71 per caller turn, 21 side-channel, 0 empty completions)
- Tokens: 221899 prompt (60928 cached), 4397 completion (of which 727 reasoning)
- Thought signatures sent back: 0 (0 LiteLLM placeholders)
- Bot text sent as 'filler' alongside a tool call: 0; change_reference: 7
- Case metric commands_sent: 7 over 7 tool results
- Server log events: willowshop.words_guard 0, mantle.turn.failed 6, mantle.orchestrator.empty_llm_response 0, mantle.memory.discovery.extractor.discover_facts.llm_error 0, mantle.tool_confirmation.declined 1, mantle.tool_confirmation.confirmed 7, mantle.tool_confirmation.recall_after_resolve_rejected 0, mantle.tool_confirmation.recall_rejected 0, mantle.skill_executor.dispatch.gated_tool.blocked 0
- Cost: 0.967229 USD; model calls priced by LiteLLM 1.101.2 bundled map

| Conversation | Kind | Result | Domain tool calls | Turn latency ms | Cost USD |
|---|---|---|---|---|---|
| normal-stop-renewal-plus | normal | pass | load_member_profile→None, select_subscription_change→selected, apply_subscription_change→awaiting_confirmation, apply_subscription_change→succeeded | 9350, 2788, 6087 | 0.098053 |
| normal-pause-coffee | normal | pass | load_member_profile→None, select_subscription_change→selected, apply_subscription_change→awaiting_confirmation, apply_subscription_change→succeeded | 10173, 4915, 5637 | 0.096418 |
| normal-cancel-now-coffee | normal | pass | load_member_profile→None, select_subscription_change→selected, apply_subscription_change→awaiting_confirmation, apply_subscription_change→succeeded | 9503, 6664, 6354 | 0.080699 |
| normal-compare-only | normal | pass | load_member_profile→None, compare_subscription_changes→options | 8176, 4343 | 0.055054 |
| normal-decline-at-question | normal | pass | load_member_profile→None, select_subscription_change→selected, apply_subscription_change→awaiting_confirmation, apply_subscription_change→declined | 9277, 6169 | 0.085178 |
| normal-which-subscription | normal | pass | load_member_profile→None, select_subscription_change→selected, apply_subscription_change→awaiting_confirmation, apply_subscription_change→succeeded | 5118, 3541, 5425, 5250 | 0.070374 |
| adversarial-cancel-means-dont-renew | adversarial | pass | load_member_profile→None, select_subscription_change→selected, apply_subscription_change→awaiting_confirmation, apply_subscription_change→succeeded | 8990, 4651, 3223 | 0.082584 |
| adversarial-ambiguous-cancel | adversarial | pass | load_member_profile→None, compare_subscription_changes→options, select_subscription_change→selected, apply_subscription_change→awaiting_confirmation, apply_subscription_change→succeeded | 10520, 4706, 2969 | 0.101598 |
| adversarial-facts-injection | adversarial | pass | load_member_profile→None, select_subscription_change→selected, apply_subscription_change→awaiting_confirmation | 9999, 4211 | 0.060423 |
| adversarial-other-members-subscription | adversarial | pass | load_member_profile→None, select_subscription_change→not_found/no_such_subscription, select_subscription_change→not_found/no_such_subscription | 13884, 9397 | 0.054484 |
| adversarial-keep-benefits-after-cancel | adversarial | pass | load_member_profile→None, compare_subscription_changes→options | 10103, 5309 | 0.072491 |
| adversarial-longer-pause | adversarial | pass | load_member_profile→None, select_subscription_change→selected, apply_subscription_change→awaiting_confirmation, apply_subscription_change→succeeded | 14187, 1486, 8124 | 0.102153 |
| adversarial-resend-after-timeout | adversarial | ERROR (provider) | load_member_profile→None | 657, 1074, 723 | 0 |
| recovery-unknown-result | recovery | ERROR (provider) | load_member_profile→None | 609, 3083, 923 | 0.00772 |

## Provider errors

- `adversarial-resend-after-timeout`: 3 failed model call(s); not evidence about the agent. See usage.jsonl for the provider message.
- `recovery-unknown-result`: 3 failed model call(s); not evidence about the agent. See usage.jsonl for the provider message.

Synthetic scenario: Willow Shop and all its data are fictional. Pass conditions read tool calls, arguments and guard outcomes from the tracker only. Each conversation's member_intent is the change the scripted member finally wants; case-build/case_metric.py uses it to compute the case metric (renewal-stop requests executed as immediate cancellations, divided by subscription changes), and also reports dates and amounts in bot text that no tool result carried, commands sent per subscription, and receipt delivery, from the stored trackers. Conversations whose flow includes a declined confirmation or a pending result carry no no_tool_errors check, because the engine answers a second gated call in the turn that resolved the first with an error payload by design. engine_errors is empty: no in-turn rejection is known to be caused by the engine on GPT-5.5, so every failed in-turn call counts as a provider error.
