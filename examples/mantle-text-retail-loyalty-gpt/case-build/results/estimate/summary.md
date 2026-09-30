# retail-loyalty-gpt-text: run summary

- Case: `retail-loyalty`; channel: rest; model: `openai/gpt-5.5-2026-04-23` (provider reported gpt-5.5-2026-04-23)
- Run: 2026-09-30T19:14:24Z to 2026-09-30T19:15:03Z
- Conversations: 1 run, 1 passed, 0 failed
- Caller turns: 5; turn latency p50 4367.8 ms, p95 10301.5 ms, max 10301.5 ms
- LLM calls: 12 (2.4 per caller turn, 1 side-channel, 0 empty completions)
- Tokens: 38883 prompt (12288 cached), 546 completion (of which 102 reasoning)
- Thought signatures sent back: 0 (0 LiteLLM placeholders)
- Bot text sent as 'filler' alongside a tool call: 0; change_reference: 1
- Case metric commands_sent: 1 over 2 tool results
- Server log events: willowshop.words_guard 0, mantle.turn.failed 0, mantle.orchestrator.empty_llm_response 0, mantle.memory.discovery.extractor.discover_facts.llm_error 0, mantle.tool_confirmation.declined 0, mantle.tool_confirmation.confirmed 2, mantle.tool_confirmation.recall_after_resolve_rejected 0, mantle.tool_confirmation.recall_rejected 0, mantle.skill_executor.dispatch.gated_tool.blocked 0
- Cost: 0.155499 USD; model calls priced by LiteLLM 1.101.2 bundled map

| Conversation | Kind | Result | Domain tool calls | Turn latency ms | Cost USD |
|---|---|---|---|---|---|
| recovery-stale-revision | recovery | pass | load_member_profile→None, select_subscription_change→selected, apply_subscription_change→awaiting_confirmation, apply_subscription_change→blocked/benefit_loss_hidden, select_subscription_change→selected, select_subscription_change→selected, apply_subscription_change→awaiting_confirmation, apply_subscription_change→succeeded | 10302, 7354, 4368, 1584, 3757 | 0.155499 |

Synthetic scenario: Willow Shop and all its data are fictional. Pass conditions read tool calls, arguments and guard outcomes from the tracker only. Each conversation's member_intent is the change the scripted member finally wants; case-build/case_metric.py uses it to compute the case metric (renewal-stop requests executed as immediate cancellations, divided by subscription changes), and also reports dates and amounts in bot text that no tool result carried, commands sent per subscription, and receipt delivery, from the stored trackers. Conversations whose flow includes a declined confirmation or a pending result carry no no_tool_errors check, because the engine answers a second gated call in the turn that resolved the first with an error payload by design. engine_errors is empty: no in-turn rejection is known to be caused by the engine on GPT-5.5, so every failed in-turn call counts as a provider error.
