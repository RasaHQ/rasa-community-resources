# telco-retention-gpt-text: run summary

- Case: `telco-retention`; channel: rest; model: `openai/gpt-5.5-2026-04-23` (provider reported gpt-5.5-2026-04-23)
- Run: 2026-10-01T23:42:52Z to 2026-10-01T23:51:25Z
- Conversations: 20 run, 20 passed, 0 failed
- Caller turns: 20; turn latency p50 11561.8 ms, p95 14314.9 ms, max 17645.8 ms
- LLM calls: 97 (4.85 per caller turn, 20 side-channel, 0 empty completions)
- Tokens: 217296 prompt (122880 cached), 7085 completion (of which 2578 reasoning)
- Thought signatures sent back: 0 (0 LiteLLM placeholders)
- Bot text sent as 'filler' alongside a tool call: 0; offer_prompt: 0; closure_claim: 0; cancellation_reference: 37; offer_reference: 0
- Case metric offers_recorded: 0 over 0 tool results
- Server log events: juniper.offer_words_guard 0, mantle.turn.failed 0, mantle.orchestrator.empty_llm_response 0, mantle.memory.discovery.extractor.discover_facts.llm_error 0, mantle.tool_confirmation.declined 0, mantle.tool_confirmation.confirmed 0, mantle.tool_confirmation.recall_after_resolve_rejected 0, mantle.tool_confirmation.recall_rejected 0, mantle.skill_executor.dispatch.gated_tool.blocked 0
- Cost: 0.74607 USD; model calls priced by LiteLLM 1.101.2 bundled map

| Conversation | Kind | Result | Domain tool calls | Turn latency ms | Cost USD |
|---|---|---|---|---|---|
| recovery-fibre-withdrawn-on-record-r01 | recovery | pass | load_customer_profile→None, record_cancellation_request→recorded/intake_is_not_action_approval, get_retention_offer→blocked/contact_withdrawn | 17646 | 0.055001 |
| recovery-fibre-withdrawn-on-record-r02 | recovery | pass | load_customer_profile→None, record_cancellation_request→recorded/intake_is_not_action_approval, get_retention_offer→blocked/contact_withdrawn | 11562 | 0.031351 |
| recovery-fibre-withdrawn-on-record-r03 | recovery | pass | load_customer_profile→None, record_cancellation_request→recorded/intake_is_not_action_approval, get_retention_offer→blocked/contact_withdrawn | 12351 | 0.056981 |
| recovery-fibre-withdrawn-on-record-r04 | recovery | pass | load_customer_profile→None, record_cancellation_request→recorded/intake_is_not_action_approval | 7747 | 0.021606 |
| recovery-fibre-withdrawn-on-record-r05 | recovery | pass | load_customer_profile→None, record_cancellation_request→recorded/intake_is_not_action_approval | 7849 | 0.021276 |
| recovery-fibre-withdrawn-on-record-r06 | recovery | pass | load_customer_profile→None, record_cancellation_request→recorded/intake_is_not_action_approval, get_retention_offer→blocked/contact_withdrawn | 12140 | 0.034494 |
| recovery-fibre-withdrawn-on-record-r07 | recovery | pass | load_customer_profile→None, record_cancellation_request→recorded/intake_is_not_action_approval, get_retention_offer→blocked/contact_withdrawn | 13465 | 0.041437 |
| recovery-fibre-withdrawn-on-record-r08 | recovery | pass | load_customer_profile→None, record_cancellation_request→recorded/intake_is_not_action_approval, get_retention_offer→blocked/contact_withdrawn | 11216 | 0.036673 |
| recovery-fibre-withdrawn-on-record-r09 | recovery | pass | load_customer_profile→None, record_cancellation_request→recorded/intake_is_not_action_approval, get_retention_offer→blocked/contact_withdrawn | 12232 | 0.036339 |
| recovery-fibre-withdrawn-on-record-r10 | recovery | pass | load_customer_profile→None, record_cancellation_request→recorded/intake_is_not_action_approval, get_retention_offer→blocked/contact_withdrawn | 12793 | 0.033861 |
| recovery-fibre-withdrawn-on-record-r11 | recovery | pass | load_customer_profile→None, record_cancellation_request→recorded/intake_is_not_action_approval | 10364 | 0.032491 |
| recovery-fibre-withdrawn-on-record-r12 | recovery | pass | load_customer_profile→None, record_cancellation_request→recorded/intake_is_not_action_approval, get_retention_offer→blocked/contact_withdrawn | 13615 | 0.041846 |
| recovery-fibre-withdrawn-on-record-r13 | recovery | pass | load_customer_profile→None, record_cancellation_request→recorded/intake_is_not_action_approval, get_retention_offer→blocked/contact_withdrawn | 10384 | 0.031216 |
| recovery-fibre-withdrawn-on-record-r14 | recovery | pass | load_customer_profile→None, record_cancellation_request→recorded/intake_is_not_action_approval, get_retention_offer→blocked/contact_withdrawn | 12016 | 0.032331 |
| recovery-fibre-withdrawn-on-record-r15 | recovery | pass | load_customer_profile→None, record_cancellation_request→recorded/intake_is_not_action_approval, get_retention_offer→blocked/contact_withdrawn | 12031 | 0.038317 |
| recovery-fibre-withdrawn-on-record-r16 | recovery | pass | load_customer_profile→None, record_cancellation_request→recorded/intake_is_not_action_approval, get_retention_offer→blocked/contact_withdrawn | 9724 | 0.037273 |
| recovery-fibre-withdrawn-on-record-r17 | recovery | pass | load_customer_profile→None, record_cancellation_request→recorded/intake_is_not_action_approval, get_retention_offer→blocked/contact_withdrawn | 14315 | 0.044506 |
| recovery-fibre-withdrawn-on-record-r18 | recovery | pass | load_customer_profile→None, record_cancellation_request→recorded/intake_is_not_action_approval, get_retention_offer→blocked/contact_withdrawn | 10044 | 0.035818 |
| recovery-fibre-withdrawn-on-record-r19 | recovery | pass | load_customer_profile→None, record_cancellation_request→recorded/intake_is_not_action_approval, get_retention_offer→blocked/contact_withdrawn | 11112 | 0.038887 |
| recovery-fibre-withdrawn-on-record-r20 | recovery | pass | load_customer_profile→None, record_cancellation_request→recorded/intake_is_not_action_approval, get_retention_offer→blocked/contact_withdrawn | 10804 | 0.044366 |

Synthetic scenario: Juniper Mobile and all its data are fictional. The target channel is Telegram; every run is web chat over local REST. Pass conditions read tool calls, arguments and results from the tracker only. offer_prompt and closure_claim are read from bot text (straight and typographic apostrophes) and reported separately from pass/fail; case-build/case_metric.py computes the case metric (offer prompts after a clear refusal, divided by sessions containing refusal) and receipt delivery from the stored trackers. Conversations whose customer answers the engine's question with a refusal carry no no_tool_errors check, because the engine answers a second gated call in the turn that resolved the first with an error payload by design. engine_errors is empty: no in-turn rejection is known to be caused by the engine on GPT-5.5, so every failed in-turn call counts as a provider error.
