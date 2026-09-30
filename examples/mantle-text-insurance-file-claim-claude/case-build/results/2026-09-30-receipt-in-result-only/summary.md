# insurance-file-claim-claude-text: run summary

- Case: `insurance-file-claim`; channel: rest; model: `anthropic/claude-sonnet-5-5` (provider reported claude-sonnet-5-5)
- Run: 2026-09-30T07:08:03Z to 2026-09-30T07:10:18Z
- Variant `receipt-in-result-only`: The tools do not send the customer the receipt themselves; the claim reference is only in the tool result, as in the earlier builds
- Conversations: 6 run, 6 passed, 0 failed
- Caller turns: 19; turn latency p50 5276.5 ms, p95 10535.5 ms, max 10535.5 ms
- LLM calls: 64 (3.37 per caller turn, 11 side-channel, 0 empty completions, 11 failed side-channel calls)
- Tokens: 313881 prompt (124056 cached, 99471 written to cache), 7808 completion (of which 2873 reasoning)
- Thought signatures sent back: 0 (0 LiteLLM placeholders)
- Bot text sent as 'filler' alongside a tool call: 0; filed_claim: 4; coverage_promise: 0
- Case metric claims_filed: 6 over 6 tool results
- Server log events: mantle.turn.failed 0, mantle.orchestrator.empty_llm_response 0, mantle.memory.discovery.extractor.discover_facts.llm_error 11, mantle.tool_confirmation.declined 1, mantle.tool_confirmation.confirmed 6, mantle.tool_confirmation.recall_after_resolve_rejected 0, mantle.tool_confirmation.recall_rejected 0, mantle.skill_executor.dispatch.gated_tool.blocked 0, harborcover.turn_order_fix 6
- Cost: 0.532277 USD; model calls priced by LiteLLM 1.101.2 from the vendor's published price (https://platform.claude.com/docs/en/about-claude/pricing (Claude Sonnet 5.5: $2 / MTok base input, $2.50 / MTok 5m cache writes, $0.20 / MTok cache hits, $10 / MTok output), checked 2026-09-29), because its bundled map has no row for this model

| Conversation | Kind | Result | Domain tool calls | Turn latency ms | Cost USD |
|---|---|---|---|---|---|
| normal-water-leak-all-received | normal | pass | load_session_customer→None, start_claim_draft→drafted, check_attachments→checked, submit_claim_report→awaiting_confirmation, submit_claim_report→succeeded/verified_fixture_receipt | 7703, 5522, 5182 | 0.110725 |
| normal-failed-upload-follow-up | normal | pass | load_session_customer→None, start_claim_draft→drafted, check_attachments→checked, submit_claim_report→awaiting_confirmation, submit_claim_report→succeeded/verified_fixture_receipt | 10536, 6101, 3355 | 0.076285 |
| normal-theft-ownership-to-follow | normal | pass | load_session_customer→None, start_claim_draft→drafted, check_attachments→checked, submit_claim_report→awaiting_confirmation, submit_claim_report→succeeded/verified_fixture_receipt | 9528, 3416, 2752 | 0.058512 |
| recovery-ack-lost-auto | recovery | pass | load_session_customer→None, start_claim_draft→drafted, check_attachments→checked, submit_claim_report→awaiting_confirmation, submit_claim_report→pending/submission_not_acknowledged, check_claim_submission→acknowledged/found_by_draft_id | 8020, 5242, 2723 | 0.093313 |
| recovery-service-unavailable-landlord | recovery | pass | load_session_customer→None, start_claim_draft→drafted, check_attachments→checked, submit_claim_report→awaiting_confirmation, submit_claim_report→pending/submission_not_acknowledged, check_claim_submission→unknown/claims_system_unavailable, route_claims_intake→routed/Customer confirmed the report, but the claims system did not acknowledge the submission and cannot confirm whether it was filed. Draft retained. | 8289, 8968, 4294 | 0.078667 |
| correction-date-at-confirmation | correction | pass | load_session_customer→None, start_claim_draft→drafted, check_attachments→checked, submit_claim_report→awaiting_confirmation, submit_claim_report→declined, update_claim_draft→updated, submit_claim_report→awaiting_confirmation, submit_claim_report→succeeded/verified_fixture_receipt | 7438, 2999, 1417, 5276 | 0.114774 |

Synthetic scenario: HarborCover, its policyholders, policies and files are fictional. Pass conditions read tool calls, arguments and guard outcomes from the tracker only; filed_claim and coverage_promise are read from bot text and reported separately from pass/fail, and case-build/case_metric.py joins claim references in bot text to the tool results for receipt delivery. Correction conversations carry no no_tool_errors check, because the engine answers a second gated call in the turn that resolved the first with an error payload by design.
