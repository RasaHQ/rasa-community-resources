# telco-retention-gpt-text: run summary

- Case: `telco-retention`; channel: rest; model: `openai/gpt-5.5-2026-04-23` (provider reported gpt-5.5-2026-04-23)
- Run: 2026-10-01T23:55:42Z to 2026-10-02T00:00:49Z
- Variant `consent-no-dispatch-note`: Consent experiment (c): the campaign is still paused, but record_cancellation_request leaves the campaign_dispatch note out of its result; next_step as shipped
- Conversations: 20 run, 0 passed, 20 failed
- Caller turns: 20; turn latency p50 10698.6 ms, p95 13079.9 ms, max 13445.4 ms
- LLM calls: 97 (4.85 per caller turn, 20 side-channel, 0 empty completions)
- Tokens: 214653 prompt (134144 cached), 6737 completion (of which 2490 reasoning)
- Thought signatures sent back: 0 (0 LiteLLM placeholders)
- Bot text sent as 'filler' alongside a tool call: 0; offer_prompt: 0; closure_claim: 0; cancellation_reference: 37; offer_reference: 0
- Case metric offers_recorded: 0 over 0 tool results
- Server log events: juniper.offer_words_guard 0, mantle.turn.failed 0, mantle.orchestrator.empty_llm_response 0, mantle.memory.discovery.extractor.discover_facts.llm_error 0, mantle.tool_confirmation.declined 0, mantle.tool_confirmation.confirmed 0, mantle.tool_confirmation.recall_after_resolve_rejected 0, mantle.tool_confirmation.recall_rejected 0, mantle.skill_executor.dispatch.gated_tool.blocked 0
- Cost: 0.671727 USD; model calls priced by LiteLLM 1.101.2 bundled map

| Conversation | Kind | Result | Domain tool calls | Turn latency ms | Cost USD |
|---|---|---|---|---|---|
| recovery-fibre-withdrawn-on-record-r01 | recovery | FAIL | load_customer_profile→None, record_cancellation_request→recorded/intake_is_not_action_approval, get_retention_offer→blocked/contact_withdrawn | 12260 | 0.043394 |
| recovery-fibre-withdrawn-on-record-r02 | recovery | FAIL | load_customer_profile→None, record_cancellation_request→recorded/intake_is_not_action_approval, get_retention_offer→blocked/contact_withdrawn | 11067 | 0.032716 |
| recovery-fibre-withdrawn-on-record-r03 | recovery | FAIL | load_customer_profile→None, record_cancellation_request→recorded/intake_is_not_action_approval, get_retention_offer→blocked/contact_withdrawn | 11019 | 0.034374 |
| recovery-fibre-withdrawn-on-record-r04 | recovery | FAIL | load_customer_profile→None, record_cancellation_request→recorded/intake_is_not_action_approval, get_retention_offer→blocked/contact_withdrawn | 9381 | 0.038372 |
| recovery-fibre-withdrawn-on-record-r05 | recovery | FAIL | load_customer_profile→None, record_cancellation_request→recorded/intake_is_not_action_approval, get_retention_offer→blocked/contact_withdrawn | 10550 | 0.036713 |
| recovery-fibre-withdrawn-on-record-r06 | recovery | FAIL | load_customer_profile→None, record_cancellation_request→recorded/intake_is_not_action_approval | 7083 | 0.019481 |
| recovery-fibre-withdrawn-on-record-r07 | recovery | FAIL | load_customer_profile→None, record_cancellation_request→recorded/intake_is_not_action_approval, get_retention_offer→blocked/contact_withdrawn | 13445 | 0.037208 |
| recovery-fibre-withdrawn-on-record-r08 | recovery | FAIL | load_customer_profile→None, record_cancellation_request→recorded/intake_is_not_action_approval | 8187 | 0.019881 |
| recovery-fibre-withdrawn-on-record-r09 | recovery | FAIL | load_customer_profile→None, record_cancellation_request→recorded/intake_is_not_action_approval, get_retention_offer→blocked/contact_withdrawn | 12795 | 0.048854 |
| recovery-fibre-withdrawn-on-record-r10 | recovery | FAIL | load_customer_profile→None, record_cancellation_request→recorded/intake_is_not_action_approval, get_retention_offer→blocked/contact_withdrawn | 12164 | 0.032606 |
| recovery-fibre-withdrawn-on-record-r11 | recovery | FAIL | load_customer_profile→None, record_cancellation_request→recorded/intake_is_not_action_approval, get_retention_offer→blocked/contact_withdrawn | 10232 | 0.028166 |
| recovery-fibre-withdrawn-on-record-r12 | recovery | FAIL | load_customer_profile→None, record_cancellation_request→recorded/intake_is_not_action_approval, get_retention_offer→blocked/contact_withdrawn | 12664 | 0.038433 |
| recovery-fibre-withdrawn-on-record-r13 | recovery | FAIL | load_customer_profile→None, record_cancellation_request→recorded/intake_is_not_action_approval, get_retention_offer→blocked/contact_withdrawn | 10699 | 0.046049 |
| recovery-fibre-withdrawn-on-record-r14 | recovery | FAIL | load_customer_profile→None, record_cancellation_request→recorded/intake_is_not_action_approval, get_retention_offer→blocked/contact_withdrawn | 11738 | 0.032316 |
| recovery-fibre-withdrawn-on-record-r15 | recovery | FAIL | load_customer_profile→None, record_cancellation_request→recorded/intake_is_not_action_approval, get_retention_offer→blocked/contact_withdrawn | 11417 | 0.029306 |
| recovery-fibre-withdrawn-on-record-r16 | recovery | FAIL | load_customer_profile→None, record_cancellation_request→recorded/intake_is_not_action_approval, get_retention_offer→blocked/contact_withdrawn | 13080 | 0.028921 |
| recovery-fibre-withdrawn-on-record-r17 | recovery | FAIL | load_customer_profile→None, record_cancellation_request→recorded/intake_is_not_action_approval, get_retention_offer→blocked/contact_withdrawn | 10494 | 0.038362 |
| recovery-fibre-withdrawn-on-record-r18 | recovery | FAIL | load_customer_profile→None, record_cancellation_request→recorded/intake_is_not_action_approval | 7907 | 0.027658 |
| recovery-fibre-withdrawn-on-record-r19 | recovery | FAIL | load_customer_profile→None, record_cancellation_request→recorded/intake_is_not_action_approval, get_retention_offer→blocked/contact_withdrawn | 10268 | 0.030256 |
| recovery-fibre-withdrawn-on-record-r20 | recovery | FAIL | load_customer_profile→None, record_cancellation_request→recorded/intake_is_not_action_approval, get_retention_offer→blocked/contact_withdrawn | 8927 | 0.028661 |

## Failed checks

- `recovery-fibre-withdrawn-on-record-r01`: {"type": "tool_called", "tool": "record_cancellation_request", "result": {"status": "recorded", "service_id": "JM-FIB-204419", "campaign_dispatch": {"campaign": "paused for this account"}}} (0 matching call(s), need >= 1)
- `recovery-fibre-withdrawn-on-record-r02`: {"type": "tool_called", "tool": "record_cancellation_request", "result": {"status": "recorded", "service_id": "JM-FIB-204419", "campaign_dispatch": {"campaign": "paused for this account"}}} (0 matching call(s), need >= 1)
- `recovery-fibre-withdrawn-on-record-r03`: {"type": "tool_called", "tool": "record_cancellation_request", "result": {"status": "recorded", "service_id": "JM-FIB-204419", "campaign_dispatch": {"campaign": "paused for this account"}}} (0 matching call(s), need >= 1)
- `recovery-fibre-withdrawn-on-record-r04`: {"type": "tool_called", "tool": "record_cancellation_request", "result": {"status": "recorded", "service_id": "JM-FIB-204419", "campaign_dispatch": {"campaign": "paused for this account"}}} (0 matching call(s), need >= 1)
- `recovery-fibre-withdrawn-on-record-r05`: {"type": "tool_called", "tool": "record_cancellation_request", "result": {"status": "recorded", "service_id": "JM-FIB-204419", "campaign_dispatch": {"campaign": "paused for this account"}}} (0 matching call(s), need >= 1)
- `recovery-fibre-withdrawn-on-record-r06`: {"type": "tool_called", "tool": "record_cancellation_request", "result": {"status": "recorded", "service_id": "JM-FIB-204419", "campaign_dispatch": {"campaign": "paused for this account"}}} (0 matching call(s), need >= 1)
- `recovery-fibre-withdrawn-on-record-r07`: {"type": "tool_called", "tool": "record_cancellation_request", "result": {"status": "recorded", "service_id": "JM-FIB-204419", "campaign_dispatch": {"campaign": "paused for this account"}}} (0 matching call(s), need >= 1)
- `recovery-fibre-withdrawn-on-record-r08`: {"type": "tool_called", "tool": "record_cancellation_request", "result": {"status": "recorded", "service_id": "JM-FIB-204419", "campaign_dispatch": {"campaign": "paused for this account"}}} (0 matching call(s), need >= 1)
- `recovery-fibre-withdrawn-on-record-r09`: {"type": "tool_called", "tool": "record_cancellation_request", "result": {"status": "recorded", "service_id": "JM-FIB-204419", "campaign_dispatch": {"campaign": "paused for this account"}}} (0 matching call(s), need >= 1)
- `recovery-fibre-withdrawn-on-record-r10`: {"type": "tool_called", "tool": "record_cancellation_request", "result": {"status": "recorded", "service_id": "JM-FIB-204419", "campaign_dispatch": {"campaign": "paused for this account"}}} (0 matching call(s), need >= 1)
- `recovery-fibre-withdrawn-on-record-r11`: {"type": "tool_called", "tool": "record_cancellation_request", "result": {"status": "recorded", "service_id": "JM-FIB-204419", "campaign_dispatch": {"campaign": "paused for this account"}}} (0 matching call(s), need >= 1)
- `recovery-fibre-withdrawn-on-record-r12`: {"type": "tool_called", "tool": "record_cancellation_request", "result": {"status": "recorded", "service_id": "JM-FIB-204419", "campaign_dispatch": {"campaign": "paused for this account"}}} (0 matching call(s), need >= 1)
- `recovery-fibre-withdrawn-on-record-r13`: {"type": "tool_called", "tool": "record_cancellation_request", "result": {"status": "recorded", "service_id": "JM-FIB-204419", "campaign_dispatch": {"campaign": "paused for this account"}}} (0 matching call(s), need >= 1)
- `recovery-fibre-withdrawn-on-record-r14`: {"type": "tool_called", "tool": "record_cancellation_request", "result": {"status": "recorded", "service_id": "JM-FIB-204419", "campaign_dispatch": {"campaign": "paused for this account"}}} (0 matching call(s), need >= 1)
- `recovery-fibre-withdrawn-on-record-r15`: {"type": "tool_called", "tool": "record_cancellation_request", "result": {"status": "recorded", "service_id": "JM-FIB-204419", "campaign_dispatch": {"campaign": "paused for this account"}}} (0 matching call(s), need >= 1)
- `recovery-fibre-withdrawn-on-record-r16`: {"type": "tool_called", "tool": "record_cancellation_request", "result": {"status": "recorded", "service_id": "JM-FIB-204419", "campaign_dispatch": {"campaign": "paused for this account"}}} (0 matching call(s), need >= 1)
- `recovery-fibre-withdrawn-on-record-r17`: {"type": "tool_called", "tool": "record_cancellation_request", "result": {"status": "recorded", "service_id": "JM-FIB-204419", "campaign_dispatch": {"campaign": "paused for this account"}}} (0 matching call(s), need >= 1)
- `recovery-fibre-withdrawn-on-record-r18`: {"type": "tool_called", "tool": "record_cancellation_request", "result": {"status": "recorded", "service_id": "JM-FIB-204419", "campaign_dispatch": {"campaign": "paused for this account"}}} (0 matching call(s), need >= 1)
- `recovery-fibre-withdrawn-on-record-r19`: {"type": "tool_called", "tool": "record_cancellation_request", "result": {"status": "recorded", "service_id": "JM-FIB-204419", "campaign_dispatch": {"campaign": "paused for this account"}}} (0 matching call(s), need >= 1)
- `recovery-fibre-withdrawn-on-record-r20`: {"type": "tool_called", "tool": "record_cancellation_request", "result": {"status": "recorded", "service_id": "JM-FIB-204419", "campaign_dispatch": {"campaign": "paused for this account"}}} (0 matching call(s), need >= 1)

Synthetic scenario: Juniper Mobile and all its data are fictional. The target channel is Telegram; every run is web chat over local REST. Pass conditions read tool calls, arguments and results from the tracker only. offer_prompt and closure_claim are read from bot text (straight and typographic apostrophes) and reported separately from pass/fail; case-build/case_metric.py computes the case metric (offer prompts after a clear refusal, divided by sessions containing refusal) and receipt delivery from the stored trackers. Conversations whose customer answers the engine's question with a refusal carry no no_tool_errors check, because the engine answers a second gated call in the turn that resolved the first with an error payload by design. engine_errors is empty: no in-turn rejection is known to be caused by the engine on GPT-5.5, so every failed in-turn call counts as a provider error.
