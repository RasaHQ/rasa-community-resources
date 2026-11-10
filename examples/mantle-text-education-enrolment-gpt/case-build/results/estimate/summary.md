# education-enrolment-gpt-text: run summary

- Case: `education-enrolment`; channel: rest; model: `openai/gpt-5.5-2026-04-23` (provider reported gpt-5.5-2026-04-23)
- Run: 2026-09-30T18:05:02Z to 2026-09-30T18:05:44Z
- Conversations: 1 run, 1 passed, 0 failed
- Caller turns: 3; turn latency p50 10638.3 ms, p95 14646.5 ms, max 14646.5 ms
- LLM calls: 10 (3.33 per caller turn, 1 side-channel, 0 empty completions)
- Tokens: 31640 prompt (14848 cached), 572 completion (of which 195 reasoning)
- Thought signatures sent back: 0 (0 LiteLLM placeholders)
- Bot text sent as 'filler' alongside a tool call: 0; aid_award_claim: 0; admission_claim: 0; extension_claim: 0; support_reference: 1
- Case metric enquiries_recorded: 1 over 1 tool results
- Server log events: pine.words_guard 0, mantle.turn.failed 0, mantle.orchestrator.empty_llm_response 0, mantle.memory.discovery.extractor.discover_facts.llm_error 0, mantle.tool_confirmation.declined 0, mantle.tool_confirmation.confirmed 1, mantle.tool_confirmation.recall_after_resolve_rejected 0, mantle.tool_confirmation.recall_rejected 0, mantle.skill_executor.dispatch.gated_tool.blocked 0
- Cost: 0.108544 USD; model calls priced by LiteLLM 1.101.2 bundled map

| Conversation | Kind | Result | Domain tool calls | Turn latency ms | Cost USD |
|---|---|---|---|---|---|
| correction-after-recorded | correction | pass | load_applicant_profile→None, lookup_application→found, record_enquiry→awaiting_confirmation, record_enquiry→succeeded/verified_fixture_receipt, lookup_application→blocked/submission_as_award, route_to_team→routed | 10638, 4878, 14646 | 0.108544 |

Synthetic scenario: Pine University, its applicants, applications, teams and dates are fictional. Pass conditions read tool calls, arguments and guard outcomes from the tracker only. aid_award_claim, admission_claim and extension_claim are read from bot text (straight and typographic apostrophes) and reported separately from pass/fail; case-build/case_metric.py computes the case metric (application receipts described as admission or aid awards, per application enquiry) and receipt delivery from the stored trackers. Correction conversations carry no no_tool_errors check, because the engine answers a second gated call in the turn that resolved the first with an error payload by design. engine_errors is empty: no in-turn rejection is known to be caused by the engine on GPT-5.5, so every failed in-turn call counts as a provider error.
