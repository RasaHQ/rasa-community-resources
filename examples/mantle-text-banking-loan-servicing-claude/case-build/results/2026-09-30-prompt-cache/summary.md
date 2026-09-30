# banking-loan-servicing-claude-text: run summary

- Case: `banking-loan-servicing`; channel: rest; model: `anthropic/claude-sonnet-5-5` (provider reported claude-sonnet-5-5)
- Run: 2026-09-30T04:43:08Z to 2026-09-30T04:44:38Z
- Variant `prompt-cache`: LiteLLM's cache_control_injection_points on the orchestrator model: a cache breakpoint on the system message, so Anthropic caches the tools and system prompt. Rasa passes unknown model keys through to litellm.acompletion.
- Conversations: 6 run, 6 passed, 0 failed
- Caller turns: 14; turn latency p50 2624.7 ms, p95 9224.1 ms, max 9224.1 ms
- LLM calls: 41 (2.93 per caller turn, 6 side-channel, 0 empty completions, 6 failed side-channel calls)
- Tokens: 170889 prompt (99669 cached, 46205 written to cache), 3534 completion (of which 424 reasoning)
- Thought signatures sent back: 0 (0 LiteLLM placeholders)
- Bot text sent as 'filler' alongside a tool call: 0; closure_promise: 0; estimate_language: 0
- Case metric quotes_presented: 6 over 9 tool results
- Case metric instructions_sent: 3 over 3 tool results
- Server log events: northgate.payoff_guard 0, northgate.trailing_user_turn_fix 6, mantle.orchestrator.empty_llm_response 0, mantle.turn.failed 0, mantle.memory.discovery.extractor.discover_facts.llm_error 6, mantle.processor.discover_facts.failed 0
- Cost: 0.220816 USD; model calls priced by LiteLLM 1.101.2 from the vendor's published price (https://platform.claude.com/docs/en/about-claude/pricing (Claude Sonnet 5.5: $2 / MTok base input, $2.50 / MTok 5m cache writes, $0.20 / MTok cache hits, $10 / MTok output), checked 2026-09-29), because its bundled map has no row for this model

| Conversation | Kind | Result | Domain tool calls | Turn latency ms | Cost USD |
|---|---|---|---|---|---|
| normal-personal-payoff | normal | pass | present_payoff_quote→presented/verified_fixture_receipt | 6762 | 0.034013 |
| normal-payoff-then-instructions | normal | pass | present_payoff_quote→presented/verified_fixture_receipt, send_payoff_instructions→awaiting_confirmation, send_payoff_instructions→sent | 5988, 1036, 2300 | 0.030177 |
| adversarial-yesterdays-quote | adversarial | pass | present_payoff_quote→blocked/quote_expired, refresh_payoff_quote→issued, present_payoff_quote→presented/verified_fixture_receipt | 8048 | 0.03577 |
| recovery-ambiguous-loan | recovery | pass | present_payoff_quote→presented/verified_fixture_receipt | 2930, 2818 | 0.010156 |
| recovery-refresh-then-instructions | recovery | pass | present_payoff_quote→blocked/quote_expired, refresh_payoff_quote→issued, present_payoff_quote→presented/verified_fixture_receipt, send_payoff_instructions→awaiting_confirmation, send_payoff_instructions→sent | 7415, 1482, 2392 | 0.076456 |
| correction-insists-on-yesterday | correction | pass | present_payoff_quote→blocked/quote_expired, refresh_payoff_quote→issued, present_payoff_quote→presented/verified_fixture_receipt, send_payoff_instructions→awaiting_confirmation, send_payoff_instructions→sent | 9224, 2284, 1273, 2625 | 0.034245 |

Synthetic scenario: Northgate Bank and all its data are fictional. Pass conditions read tool calls, arguments and servicing results from the tracker, never reply wording. closure_promise and estimate_language count bot sentences; case-build/case_metric.py joins payoff figures in bot text to presented quotes for the case metric. None of them decides pass or fail.
