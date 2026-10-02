# telco-retention-gpt-text: run summary

- Case: `telco-retention`; channel: rest; model: `openai/gpt-5.5-2026-04-23` (provider reported gpt-5.5-2026-04-23)
- Run: 2026-10-01T23:51:25Z to 2026-10-01T23:55:42Z
- Variant `consent-next-step-from-contact`: Consent experiment (b): record_cancellation_request computes next_step from contact_facts, so a service whose contact permission is not current gets no invitation to call get_retention_offer
- Conversations: 20 run, 20 passed, 0 failed
- Caller turns: 20; turn latency p50 7879.2 ms, p95 10296.0 ms, max 11517.0 ms
- LLM calls: 80 (4.0 per caller turn, 20 side-channel, 0 empty completions)
- Tokens: 161029 prompt (95232 cached), 4017 completion (of which 848 reasoning)
- Thought signatures sent back: 0 (0 LiteLLM placeholders)
- Bot text sent as 'filler' alongside a tool call: 0; offer_prompt: 0; closure_claim: 0; cancellation_reference: 22; offer_reference: 0
- Case metric offers_recorded: 0 over 0 tool results
- Server log events: juniper.offer_words_guard 0, mantle.turn.failed 0, mantle.orchestrator.empty_llm_response 0, mantle.memory.discovery.extractor.discover_facts.llm_error 0, mantle.tool_confirmation.declined 0, mantle.tool_confirmation.confirmed 0, mantle.tool_confirmation.recall_after_resolve_rejected 0, mantle.tool_confirmation.recall_rejected 0, mantle.skill_executor.dispatch.gated_tool.blocked 0
- Cost: 0.497111 USD; model calls priced by LiteLLM 1.101.2 bundled map

| Conversation | Kind | Result | Domain tool calls | Turn latency ms | Cost USD |
|---|---|---|---|---|---|
| recovery-fibre-withdrawn-on-record-r01 | recovery | pass | load_customer_profile→None, record_cancellation_request→recorded/intake_is_not_action_approval | 9234 | 0.025469 |
| recovery-fibre-withdrawn-on-record-r02 | recovery | pass | load_customer_profile→None, record_cancellation_request→recorded/intake_is_not_action_approval | 8241 | 0.028353 |
| recovery-fibre-withdrawn-on-record-r03 | recovery | pass | load_customer_profile→None, record_cancellation_request→recorded/intake_is_not_action_approval | 7879 | 0.021511 |
| recovery-fibre-withdrawn-on-record-r04 | recovery | pass | load_customer_profile→None, record_cancellation_request→recorded/intake_is_not_action_approval | 8034 | 0.021446 |
| recovery-fibre-withdrawn-on-record-r05 | recovery | pass | load_customer_profile→None, record_cancellation_request→recorded/intake_is_not_action_approval | 8435 | 0.020566 |
| recovery-fibre-withdrawn-on-record-r06 | recovery | pass | load_customer_profile→None, record_cancellation_request→recorded/intake_is_not_action_approval | 7528 | 0.026009 |
| recovery-fibre-withdrawn-on-record-r07 | recovery | pass | load_customer_profile→None, record_cancellation_request→recorded/intake_is_not_action_approval | 11517 | 0.032011 |
| recovery-fibre-withdrawn-on-record-r08 | recovery | pass | load_customer_profile→None, record_cancellation_request→recorded/intake_is_not_action_approval | 6956 | 0.020556 |
| recovery-fibre-withdrawn-on-record-r09 | recovery | pass | load_customer_profile→None, record_cancellation_request→recorded/intake_is_not_action_approval | 6513 | 0.027068 |
| recovery-fibre-withdrawn-on-record-r10 | recovery | pass | load_customer_profile→None, record_cancellation_request→recorded/intake_is_not_action_approval | 9138 | 0.027354 |
| recovery-fibre-withdrawn-on-record-r11 | recovery | pass | load_customer_profile→None, record_cancellation_request→recorded/intake_is_not_action_approval | 6544 | 0.020156 |
| recovery-fibre-withdrawn-on-record-r12 | recovery | pass | load_customer_profile→None, record_cancellation_request→recorded/intake_is_not_action_approval | 7234 | 0.031736 |
| recovery-fibre-withdrawn-on-record-r13 | recovery | pass | load_customer_profile→None, record_cancellation_request→recorded/intake_is_not_action_approval | 7072 | 0.020176 |
| recovery-fibre-withdrawn-on-record-r14 | recovery | pass | load_customer_profile→None, record_cancellation_request→recorded/intake_is_not_action_approval | 7392 | 0.026284 |
| recovery-fibre-withdrawn-on-record-r15 | recovery | pass | load_customer_profile→None, record_cancellation_request→recorded/intake_is_not_action_approval | 8096 | 0.025084 |
| recovery-fibre-withdrawn-on-record-r16 | recovery | pass | load_customer_profile→None, record_cancellation_request→recorded/intake_is_not_action_approval | 8295 | 0.021076 |
| recovery-fibre-withdrawn-on-record-r17 | recovery | pass | load_customer_profile→None, record_cancellation_request→recorded/intake_is_not_action_approval | 7662 | 0.020016 |
| recovery-fibre-withdrawn-on-record-r18 | recovery | pass | load_customer_profile→None, record_cancellation_request→recorded/intake_is_not_action_approval | 10296 | 0.032046 |
| recovery-fibre-withdrawn-on-record-r19 | recovery | pass | load_customer_profile→None, record_cancellation_request→recorded/intake_is_not_action_approval | 7722 | 0.027378 |
| recovery-fibre-withdrawn-on-record-r20 | recovery | pass | load_customer_profile→None, record_cancellation_request→recorded/intake_is_not_action_approval | 8915 | 0.022816 |

Synthetic scenario: Juniper Mobile and all its data are fictional. The target channel is Telegram; every run is web chat over local REST. Pass conditions read tool calls, arguments and results from the tracker only. offer_prompt and closure_claim are read from bot text (straight and typographic apostrophes) and reported separately from pass/fail; case-build/case_metric.py computes the case metric (offer prompts after a clear refusal, divided by sessions containing refusal) and receipt delivery from the stored trackers. Conversations whose customer answers the engine's question with a refusal carry no no_tool_errors check, because the engine answers a second gated call in the turn that resolved the first with an error payload by design. engine_errors is empty: no in-turn rejection is known to be caused by the engine on GPT-5.5, so every failed in-turn call counts as a provider error.
