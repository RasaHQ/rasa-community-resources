# insurance-file-claim-claude-text: run summary

- Case: `insurance-file-claim`; channel: rest; model: `anthropic/claude-sonnet-5-5` (provider reported claude-sonnet-5-5)
- Run: 2026-09-30T06:58:20Z to 2026-09-30T06:58:47Z
- Conversations: 1 run, 1 passed, 0 failed
- Caller turns: 3; turn latency p50 4483.8 ms, p95 8062.9 ms, max 8062.9 ms
- LLM calls: 11 (3.67 per caller turn, 2 side-channel, 0 empty completions, 2 failed side-channel calls)
- Tokens: 51007 prompt (9983 cached, 25165 written to cache), 1023 completion (of which 355 reasoning)
- Thought signatures sent back: 0 (0 LiteLLM placeholders)
- Bot text sent as 'filler' alongside a tool call: 0; filed_claim: 1; coverage_promise: 0
- Case metric claims_filed: 1 over 1 tool results
- Server log events: mantle.turn.failed 0, mantle.orchestrator.empty_llm_response 0, mantle.memory.discovery.extractor.discover_facts.llm_error 2, mantle.tool_confirmation.declined 0, mantle.tool_confirmation.confirmed 1, mantle.tool_confirmation.recall_after_resolve_rejected 0, mantle.tool_confirmation.recall_rejected 0, mantle.skill_executor.dispatch.gated_tool.blocked 0, harborcover.turn_order_fix 1
- Cost: 0.106857 USD; model calls priced by LiteLLM 1.101.2 from the vendor's published price (https://platform.claude.com/docs/en/about-claude/pricing (Claude Sonnet 5.5: $2 / MTok base input, $2.50 / MTok 5m cache writes, $0.20 / MTok cache hits, $10 / MTok output), checked 2026-09-29), because its bundled map has no row for this model

| Conversation | Kind | Result | Domain tool calls | Turn latency ms | Cost USD |
|---|---|---|---|---|---|
| normal-water-leak-all-received | normal | pass | load_session_customer→None, start_claim_draft→drafted, check_attachments→checked, submit_claim_report→awaiting_confirmation, submit_claim_report→succeeded/verified_fixture_receipt | 8063, 4484, 3220 | 0.106857 |

Synthetic scenario: HarborCover, its policyholders, policies and files are fictional. Pass conditions read tool calls, arguments and guard outcomes from the tracker only; filed_claim and coverage_promise are read from bot text and reported separately from pass/fail, and case-build/case_metric.py joins claim references in bot text to the tool results for receipt delivery. Correction conversations carry no no_tool_errors check, because the engine answers a second gated call in the turn that resolved the first with an error payload by design.
