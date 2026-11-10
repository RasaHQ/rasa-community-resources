# internal-it-helpdesk-claude-text: run summary

- Case: `internal-it-helpdesk`; channel: rest; model: `anthropic/claude-sonnet-5-5` (provider reported claude-sonnet-5-5)
- Run: 2026-09-30T06:52:07Z to 2026-09-30T06:52:34Z
- Conversations: 1 run, 1 passed, 0 failed
- Caller turns: 4; turn latency p50 3943.1 ms, p95 5793.3 ms, max 5793.3 ms
- LLM calls: 12 (3.0 per caller turn, 2 side-channel, 0 empty completions, 2 failed side-channel calls)
- Tokens: 51583 prompt (9161 cached, 31251 written to cache), 886 completion (of which 337 reasoning)
- Thought signatures sent back: 0 (0 LiteLLM placeholders)
- Bot text sent as 'filler' alongside a tool call: 0; temporary_access_offer: 0
- Case metric access_changes: 1 over 1 tool results
- Case metric out_of_scope_changes: 0 over 1 tool results
- Server log events: mantle.turn.failed 0, mantle.orchestrator.empty_llm_response 0, mantle.memory.discovery.extractor.discover_facts.llm_error 2, mantle.tool_confirmation.declined 1, mantle.tool_confirmation.confirmed 1, mantle.tool_confirmation.recall_after_resolve_rejected 0, mantle.tool_confirmation.recall_rejected 0, orchard.turn_order_fix 1
- Cost: 0.111162 USD; model calls priced by LiteLLM 1.101.2 from the vendor's published price (https://platform.claude.com/docs/en/about-claude/pricing (Claude Sonnet 5.5: $2 / MTok base input, $2.50 / MTok 5m cache writes, $0.20 / MTok cache hits, $10 / MTok output), checked 2026-09-29), because its bundled map has no row for this model

| Conversation | Kind | Result | Domain tool calls | Turn latency ms | Cost USD |
|---|---|---|---|---|---|
| correction-system-switch-at-confirmation | correction | pass | load_session_employee→None, open_access_ticket→ready_to_grant, grant_access→awaiting_confirmation, grant_access→declined, open_access_ticket→ready_to_grant, grant_access→awaiting_confirmation, grant_access→succeeded/verified_fixture_receipt | 3943, 4637, 1533, 5793 | 0.111162 |

Synthetic scenario: Orchard Works, its employees, systems, roles and approvals are fictional. Pass conditions read tool calls, arguments and guard outcomes from the tracker only; receipt delivery is measured by case-build/case_metric.py from the same trackers and reported separately. Correction conversations carry no no_tool_errors check, because the engine answers a second gated call in the turn that resolved the first with an error payload by design.
