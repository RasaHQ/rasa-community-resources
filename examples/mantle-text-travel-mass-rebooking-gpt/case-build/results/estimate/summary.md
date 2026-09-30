# travel-mass-rebooking-gpt-text: run summary

- Case: `travel-mass-rebooking`; channel: rest; model: `openai/gpt-5.5-2026-04-23` (provider reported gpt-5.5-2026-04-23)
- Run: 2026-09-30T17:09:16Z to 2026-09-30T17:10:18Z
- Conversations: 1 run, 1 passed, 0 failed
- Caller turns: 5; turn latency p50 10104.5 ms, p95 12178.3 ms, max 12178.3 ms
- LLM calls: 16 (3.2 per caller turn, 2 side-channel, 0 empty completions)
- Tokens: 72589 prompt (20992 cached), 954 completion (of which 90 reasoning)
- Thought signatures sent back: 0 (0 LiteLLM placeholders)
- Bot text sent as 'filler' alongside a tool call: 0; confirmed_claim: 0
- Case metric commits_with_effect: 1 over 1 tool results
- Server log events: mantle.turn.failed 0, mantle.orchestrator.empty_llm_response 0, mantle.memory.discovery.extractor.discover_facts.llm_error 0, mantle.tool_confirmation.declined 1, mantle.tool_confirmation.confirmed 1, mantle.tool_confirmation.recall_after_resolve_rejected 0, mantle.tool_confirmation.recall_rejected 0, mantle.skill_executor.dispatch.gated_tool.blocked 0
- Cost: 0.297101 USD; model calls priced by LiteLLM 1.101.2 bundled map

| Conversation | Kind | Result | Domain tool calls | Turn latency ms | Cost USD |
|---|---|---|---|---|---|
| correction-accessible-at-confirmation | correction | pass | load_passenger_profile→None, search_recovery_options→found, hold_recovery_option→held, commit_rebooking→awaiting_confirmation, commit_rebooking→declined, release_hold→released, search_recovery_options→found, hold_recovery_option→held, commit_rebooking→awaiting_confirmation, commit_rebooking→succeeded/verified_fixture_receipt | 11605, 10104, 7316, 12178, 9173 | 0.297101 |

Synthetic scenario: Horizon Travel, the storm, its flights, passengers, cases and holds are fictional. Pass conditions read tool calls, arguments and guard outcomes from the tracker only. confirmed_claim counts bot sentences that call a rebooking confirmed, from bot text, and never decides pass or fail; case-build/case_metric.py joins them to the tool results for the case metric (confirmations without committed capacity over accepted recovery offers), counts rejected holds apart from abandoned ones, and measures receipt delivery. engine_errors is empty: no in-turn rejection the engine causes on every run is known for GPT-5.5, so any failed in-turn call is a provider error. Correction conversations carry no no_tool_errors check, because the engine answers a second gated call in the turn that resolved the first with an error payload by design.
