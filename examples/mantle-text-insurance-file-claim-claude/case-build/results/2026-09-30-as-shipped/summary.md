# insurance-file-claim-claude-text: run summary

- Case: `insurance-file-claim`; channel: rest; model: `anthropic/claude-sonnet-5-5` (provider reported claude-sonnet-5-5)
- Run: 2026-09-30T06:59:32Z to 2026-09-30T07:00:22Z
- Variant `no-turn-order-hook`: Rasa as shipped for Claude: hooks.py disabled, so a request after a canned reply ends on the assistant and Claude rejects it
- Conversations: 4 run, 3 passed, 1 failed
- Caller turns: 8; turn latency p50 356.4 ms, p95 8852.4 ms, max 8852.4 ms
- LLM calls: 23 (2.88 per caller turn, 4 side-channel, 0 empty completions, 4 failed side-channel calls, 4 rejected in-turn calls matching engine_errors)
- Tokens: 85499 prompt (24808 cached, 36288 written to cache), 2065 completion (of which 832 reasoning)
- Thought signatures sent back: 0 (0 LiteLLM placeholders)
- Bot text sent as 'filler' alongside a tool call: 0; filed_claim: 2; coverage_promise: 0
- Case metric claims_filed: 2 over 2 tool results
- Server log events: mantle.turn.failed 4, mantle.orchestrator.empty_llm_response 0, mantle.memory.discovery.extractor.discover_facts.llm_error 4, mantle.tool_confirmation.declined 0, mantle.tool_confirmation.confirmed 2, mantle.tool_confirmation.recall_after_resolve_rejected 0, mantle.tool_confirmation.recall_rejected 0, mantle.skill_executor.dispatch.gated_tool.blocked 0, harborcover.turn_order_fix 0
- Cost: 0.165138 USD; model calls priced by LiteLLM 1.101.2 from the vendor's published price (https://platform.claude.com/docs/en/about-claude/pricing (Claude Sonnet 5.5: $2 / MTok base input, $2.50 / MTok 5m cache writes, $0.20 / MTok cache hits, $10 / MTok output), checked 2026-09-29), because its bundled map has no row for this model

| Conversation | Kind | Result | Domain tool calls | Turn latency ms | Cost USD |
|---|---|---|---|---|---|
| normal-water-leak-all-received | normal | pass | load_session_customer→None, start_claim_draft→drafted, check_attachments→checked, submit_claim_report→awaiting_confirmation, submit_claim_report→succeeded/verified_fixture_receipt | 356, 8165, 4143 | 0.076911 |
| normal-status-existing-claim | normal | FAIL | load_session_customer→None | 266 | 0 |
| adversarial-someone-elses-policy | adversarial | pass | load_session_customer→None | 287 | 0 |
| recovery-ack-lost-auto | recovery | pass | load_session_customer→None, start_claim_draft→drafted, check_attachments→checked, submit_claim_report→awaiting_confirmation, submit_claim_report→pending/submission_not_acknowledged, check_claim_submission→acknowledged/found_by_draft_id | 288, 8852, 7707 | 0.088226 |

## Failed checks

- `normal-status-existing-claim`: {"type": "tool_called", "tool": "check_claim_submission", "result": {"status": "filed", "claim_intake_reference": "HC-CLI-40718"}} (0 matching call(s), need >= 1)

Synthetic scenario: HarborCover, its policyholders, policies and files are fictional. Pass conditions read tool calls, arguments and guard outcomes from the tracker only; filed_claim and coverage_promise are read from bot text and reported separately from pass/fail, and case-build/case_metric.py joins claim references in bot text to the tool results for receipt delivery. Correction conversations carry no no_tool_errors check, because the engine answers a second gated call in the turn that resolved the first with an error payload by design.
