# education-enrolment-gpt-text: run summary

- Case: `education-enrolment`; channel: rest; model: `openai/gpt-5.5-2026-04-23` (provider reported gpt-5.5-2026-04-23)
- Run: 2026-09-30T18:13:56Z to 2026-09-30T18:15:30Z
- Conversations: 4 run, 3 passed, 1 failed
- Caller turns: 14; turn latency p50 4472.7 ms, p95 8675.2 ms, max 8675.2 ms
- LLM calls: 32 (2.29 per caller turn, 4 side-channel, 0 empty completions)
- Tokens: 92282 prompt (43008 cached), 1614 completion (of which 420 reasoning)
- Thought signatures sent back: 0 (0 LiteLLM placeholders)
- Bot text sent as 'filler' alongside a tool call: 0; aid_award_claim: 0; admission_claim: 0; extension_claim: 0; support_reference: 6
- Case metric enquiries_recorded: 3 over 3 tool results
- Server log events: pine.words_guard 0, mantle.turn.failed 0, mantle.orchestrator.empty_llm_response 0, mantle.memory.discovery.extractor.discover_facts.llm_error 0, mantle.tool_confirmation.declined 1, mantle.tool_confirmation.confirmed 3, mantle.tool_confirmation.recall_after_resolve_rejected 0, mantle.tool_confirmation.recall_rejected 0, mantle.skill_executor.dispatch.gated_tool.blocked 0
- Cost: 0.316294 USD; model calls priced by LiteLLM 1.101.2 bundled map

| Conversation | Kind | Result | Domain tool calls | Turn latency ms | Cost USD |
|---|---|---|---|---|---|
| normal-admission-offer | normal | pass | load_applicant_profile→None, lookup_application→found, record_enquiry→awaiting_confirmation, record_enquiry→succeeded/verified_fixture_receipt | 8675, 3616, 4130 | 0.075483 |
| normal-deadline-question | normal | pass | load_applicant_profile→None, lookup_application→found, record_enquiry→awaiting_confirmation, record_enquiry→succeeded/verified_fixture_receipt | 6090, 4242, 5865 | 0.062623 |
| correction-reference-at-confirmation | correction | pass | load_applicant_profile→None, lookup_application→found, record_enquiry→awaiting_confirmation, record_enquiry→declined, lookup_application→found, record_enquiry→awaiting_confirmation, record_enquiry→succeeded/verified_fixture_receipt | 8590, 8530, 1866, 4473 | 0.10881 |
| correction-reference-before-status | correction | FAIL | load_applicant_profile→None, lookup_application→found, lookup_application→found, record_enquiry→awaiting_confirmation | 7619, 5096, 2452, 1596 | 0.069378 |

## Failed checks

- `correction-reference-before-status`: {"type": "tool_called", "tool": "record_enquiry", "result": {"status": "succeeded", "application_reference": "AID-26-1182", "deadline_dates": "2026-10-15"}} (0 matching call(s), need >= 1)

Synthetic scenario: Pine University, its applicants, applications, teams and dates are fictional. Pass conditions read tool calls, arguments and guard outcomes from the tracker only. aid_award_claim, admission_claim and extension_claim are read from bot text (straight and typographic apostrophes) and reported separately from pass/fail; case-build/case_metric.py computes the case metric (application receipts described as admission or aid awards, per application enquiry) and receipt delivery from the stored trackers. Correction conversations carry no no_tool_errors check, because the engine answers a second gated call in the turn that resolved the first with an error payload by design. engine_errors is empty: no in-turn rejection is known to be caused by the engine on GPT-5.5, so every failed in-turn call counts as a provider error.
