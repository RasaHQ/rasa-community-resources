# telco-retention-gpt-text: run summary

- Case: `telco-retention`; channel: rest; model: `openai/gpt-5.5-2026-04-23` (provider reported gpt-5.5-2026-04-23)
- Run: 2026-09-30T19:16:31Z to 2026-09-30T19:17:44Z
- Conversations: 1 run, 1 passed, 0 failed
- Caller turns: 3; turn latency p50 6721.5 ms, p95 12011.4 ms, max 12011.4 ms
- LLM calls: 10 (3.33 per caller turn, 1 side-channel, 0 empty completions)
- Tokens: 29438 prompt (10752 cached), 535 completion (of which 256 reasoning)
- Thought signatures sent back: 0 (0 LiteLLM placeholders)
- Bot text sent as 'filler' alongside a tool call: 0; offer_prompt: 1; closure_claim: 0; cancellation_reference: 4; offer_reference: 1
- Case metric offers_recorded: 1 over 1 tool results
- Server log events: juniper.offer_words_guard 0, mantle.turn.failed 0, mantle.orchestrator.empty_llm_response 0, mantle.memory.discovery.extractor.discover_facts.llm_error 0, mantle.tool_confirmation.declined 0, mantle.tool_confirmation.confirmed 1, mantle.tool_confirmation.recall_after_resolve_rejected 0, mantle.tool_confirmation.recall_rejected 0, mantle.skill_executor.dispatch.gated_tool.blocked 0
- Cost: 0.114856 USD; model calls priced by LiteLLM 1.101.2 bundled map

| Conversation | Kind | Result | Domain tool calls | Turn latency ms | Cost USD |
|---|---|---|---|---|---|
| correction-accept-then-cancel | correction | pass | load_customer_profile→None, record_cancellation_request→recorded/intake_is_not_action_approval, get_retention_offer→offer, accept_retention_offer→awaiting_confirmation, accept_retention_offer→succeeded/verified_fixture_receipt, record_cancellation_request→recorded/intake_is_not_action_approval | 12011, 5372, 6722 | 0.114856 |

Synthetic scenario: Juniper Mobile and all its data are fictional. The target channel is Telegram; every run is web chat over local REST. Pass conditions read tool calls, arguments and results from the tracker only. offer_prompt and closure_claim are read from bot text (straight and typographic apostrophes) and reported separately from pass/fail; case-build/case_metric.py computes the case metric (offer prompts after a clear refusal, divided by sessions containing refusal) and receipt delivery from the stored trackers. Conversations whose customer answers the engine's question with a refusal carry no no_tool_errors check, because the engine answers a second gated call in the turn that resolved the first with an error payload by design. engine_errors is empty: no in-turn rejection is known to be caused by the engine on GPT-5.5, so every failed in-turn call counts as a provider error.
