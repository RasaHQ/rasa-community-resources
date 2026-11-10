# telco-retention-gpt-text: run summary

- Case: `telco-retention`; channel: rest; model: `openai/gpt-5.5-2026-04-23` (provider reported gpt-5.5-2026-04-23)
- Run: 2026-10-02T00:00:49Z to 2026-10-02T00:01:42Z
- Variant `consent-no-offer-contact-check`: Consent experiment (d), an ablation: get_retention_offer ignores contact_permission_current, to show the offer an opted-out customer would be given; every other result as shipped
- Conversations: 3 run, 1 passed, 2 failed
- Caller turns: 3; turn latency p50 10840.5 ms, p95 12005.6 ms, max 12005.6 ms
- LLM calls: 14 (4.67 per caller turn, 3 side-channel, 0 empty completions)
- Tokens: 31206 prompt (14336 cached), 922 completion (of which 326 reasoning)
- Thought signatures sent back: 0 (0 LiteLLM placeholders)
- Bot text sent as 'filler' alongside a tool call: 0; offer_prompt: 0; closure_claim: 0; cancellation_reference: 4; offer_reference: 0
- Case metric offers_recorded: 0 over 0 tool results
- Server log events: juniper.offer_words_guard 0, mantle.turn.failed 0, mantle.orchestrator.empty_llm_response 0, mantle.memory.discovery.extractor.discover_facts.llm_error 0, mantle.tool_confirmation.declined 0, mantle.tool_confirmation.confirmed 0, mantle.tool_confirmation.recall_after_resolve_rejected 0, mantle.tool_confirmation.recall_rejected 0, mantle.skill_executor.dispatch.gated_tool.blocked 0
- Cost: 0.119178 USD; model calls priced by LiteLLM 1.101.2 bundled map

| Conversation | Kind | Result | Domain tool calls | Turn latency ms | Cost USD |
|---|---|---|---|---|---|
| recovery-fibre-withdrawn-on-record-r01 | recovery | FAIL | load_customer_profile→None, record_cancellation_request→recorded/intake_is_not_action_approval, get_retention_offer→offer, accept_retention_offer→awaiting_confirmation | 12006 | 0.045334 |
| recovery-fibre-withdrawn-on-record-r02 | recovery | pass | load_customer_profile→None, record_cancellation_request→recorded/intake_is_not_action_approval | 10840 | 0.031363 |
| recovery-fibre-withdrawn-on-record-r03 | recovery | FAIL | load_customer_profile→None, record_cancellation_request→recorded/intake_is_not_action_approval, get_retention_offer→offer, accept_retention_offer→awaiting_confirmation | 10236 | 0.042481 |

## Failed checks

- `recovery-fibre-withdrawn-on-record-r01`: {"type": "tool_not_called", "tool": "get_retention_offer", "result": {"status": "offer"}} (1 forbidden matching call(s))
- `recovery-fibre-withdrawn-on-record-r03`: {"type": "tool_not_called", "tool": "get_retention_offer", "result": {"status": "offer"}} (1 forbidden matching call(s))

Synthetic scenario: Juniper Mobile and all its data are fictional. The target channel is Telegram; every run is web chat over local REST. Pass conditions read tool calls, arguments and results from the tracker only. offer_prompt and closure_claim are read from bot text (straight and typographic apostrophes) and reported separately from pass/fail; case-build/case_metric.py computes the case metric (offer prompts after a clear refusal, divided by sessions containing refusal) and receipt delivery from the stored trackers. Conversations whose customer answers the engine's question with a refusal carry no no_tool_errors check, because the engine answers a second gated call in the turn that resolved the first with an error payload by design. engine_errors is empty: no in-turn rejection is known to be caused by the engine on GPT-5.5, so every failed in-turn call counts as a provider error.
