# banking-loan-servicing-claude-text: run summary

- Case: `banking-loan-servicing`; channel: rest; model: `anthropic/claude-sonnet-5-5` (provider reported claude-sonnet-5-5)
- Run: 2026-09-30T04:32:13Z to 2026-09-30T04:32:38Z
- Conversations: 1 run, 1 passed, 0 failed
- Caller turns: 3; turn latency p50 3519.7 ms, p95 8847.0 ms, max 8847.0 ms
- LLM calls: 9 (3.0 per caller turn, 1 side-channel, 0 empty completions, 1 failed side-channel calls)
- Tokens: 41037 prompt (0 cached), 720 completion (of which 151 reasoning)
- Thought signatures sent back: 0 (0 LiteLLM placeholders)
- Bot text sent as 'filler' alongside a tool call: 0; closure_promise: 0; estimate_language: 0
- Case metric quotes_presented: 1 over 2 tool results
- Case metric instructions_sent: 1 over 1 tool results
- Server log events: northgate.payoff_guard 0, northgate.trailing_user_turn_fix 1, mantle.orchestrator.empty_llm_response 0, mantle.turn.failed 0, mantle.memory.discovery.extractor.discover_facts.llm_error 1, mantle.processor.discover_facts.failed 0
- Cost: 0.089274 USD; model calls priced by LiteLLM 1.101.2 from the vendor's published price (https://platform.claude.com/docs/en/about-claude/pricing (Claude Sonnet 5.5: $2 / MTok base input, $2.50 / MTok 5m cache writes, $0.20 / MTok cache hits, $10 / MTok output), checked 2026-09-29), because its bundled map has no row for this model

| Conversation | Kind | Result | Domain tool calls | Turn latency ms | Cost USD |
|---|---|---|---|---|---|
| recovery-refresh-then-instructions | recovery | pass | present_payoff_quote→blocked/quote_expired, refresh_payoff_quote→issued, present_payoff_quote→presented/verified_fixture_receipt, send_payoff_instructions→awaiting_confirmation, send_payoff_instructions→sent | 8847, 1186, 3520 | 0.089274 |

Synthetic scenario: Northgate Bank and all its data are fictional. Pass conditions read tool calls, arguments and servicing results from the tracker, never reply wording. closure_promise and estimate_language count bot sentences; case-build/case_metric.py joins payoff figures in bot text to presented quotes for the case metric. None of them decides pass or fail.
