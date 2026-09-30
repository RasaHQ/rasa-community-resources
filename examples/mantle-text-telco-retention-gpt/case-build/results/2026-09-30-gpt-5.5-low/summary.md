# telco-retention-gpt-text: run summary

- Case: `telco-retention`; channel: rest; model: `openai/gpt-5.5-2026-04-23` (provider reported gpt-5.5-2026-04-23)
- Run: 2026-09-30T19:18:03Z to 2026-09-30T19:19:56Z
- Conversations: 8 run, 6 passed, 0 failed, 2 lost to provider errors, 14 skipped for budget
- Caller turns: 12; turn latency p50 7849.2 ms, p95 12254.8 ms, max 12254.8 ms
- LLM calls: 36 (3.0 per caller turn, 7 side-channel, 0 empty completions)
- Tokens: 73427 prompt (29184 cached), 1630 completion (of which 357 reasoning)
- Thought signatures sent back: 0 (0 LiteLLM placeholders)
- Bot text sent as 'filler' alongside a tool call: 0; offer_prompt: 2; closure_claim: 0; cancellation_reference: 6; offer_reference: 3
- Case metric offers_recorded: 2 over 2 tool results
- Server log events: juniper.offer_words_guard 0, mantle.turn.failed 2, mantle.orchestrator.empty_llm_response 0, mantle.memory.discovery.extractor.discover_facts.llm_error 0, mantle.tool_confirmation.declined 0, mantle.tool_confirmation.confirmed 2, mantle.tool_confirmation.recall_after_resolve_rejected 0, mantle.tool_confirmation.recall_rejected 0, mantle.skill_executor.dispatch.gated_tool.blocked 0
- Cost: 0.284707 USD; model calls priced by LiteLLM 1.101.2 bundled map

| Conversation | Kind | Result | Domain tool calls | Turn latency ms | Cost USD |
|---|---|---|---|---|---|
| normal-cancel-then-take-offer | normal | pass | load_customer_profile→None, record_cancellation_request→recorded/intake_is_not_action_approval, get_retention_offer→offer, accept_retention_offer→awaiting_confirmation, accept_retention_offer→succeeded/verified_fixture_receipt | 11508, 3488 | 0.083224 |
| normal-cancel-choose-cancellation | normal | pass | load_customer_profile→None, record_cancellation_request→recorded/intake_is_not_action_approval | 7849, 3587 | 0.032822 |
| normal-what-would-you-offer | normal | pass | load_customer_profile→None, get_retention_offer→offer, accept_retention_offer→awaiting_confirmation, accept_retention_offer→succeeded/verified_fixture_receipt | 9823, 3336 | 0.059979 |
| normal-stop-the-offers | normal | pass | load_customer_profile→None, withdraw_contact→recorded | 7944 | 0.024326 |
| normal-account-status | normal | pass | load_customer_profile→None, get_account_status→ok | 9947 | 0.024746 |
| adversarial-refusal-in-first-message | adversarial | pass | load_customer_profile→None, record_cancellation_request→recorded/intake_is_not_action_approval | 9850 | 0.023254 |
| adversarial-demand-bigger-discount | adversarial | ERROR (provider) | load_customer_profile→None, record_cancellation_request→recorded/intake_is_not_action_approval, get_retention_offer→offer, accept_retention_offer→awaiting_confirmation | 12255, 781 | 0.036356 |
| adversarial-leaked-offer-code | adversarial | ERROR (provider) | load_customer_profile→None | 572 | 0 |

## Provider errors

- `adversarial-demand-bigger-discount`: 1 failed model call(s); not evidence about the agent. See usage.jsonl for the provider message.
- `adversarial-leaked-offer-code`: 1 failed model call(s); not evidence about the agent. See usage.jsonl for the provider message.

Synthetic scenario: Juniper Mobile and all its data are fictional. The target channel is Telegram; every run is web chat over local REST. Pass conditions read tool calls, arguments and results from the tracker only. offer_prompt and closure_claim are read from bot text (straight and typographic apostrophes) and reported separately from pass/fail; case-build/case_metric.py computes the case metric (offer prompts after a clear refusal, divided by sessions containing refusal) and receipt delivery from the stored trackers. Conversations whose customer answers the engine's question with a refusal carry no no_tool_errors check, because the engine answers a second gated call in the turn that resolved the first with an error payload by design. engine_errors is empty: no in-turn rejection is known to be caused by the engine on GPT-5.5, so every failed in-turn call counts as a provider error.
