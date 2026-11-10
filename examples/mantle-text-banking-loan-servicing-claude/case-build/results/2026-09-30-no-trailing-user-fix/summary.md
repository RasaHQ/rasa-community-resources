# banking-loan-servicing-claude-text: run summary

- Case: `banking-loan-servicing`; channel: rest; model: `anthropic/claude-sonnet-5-5` (provider reported n/a)
- Run: 2026-09-30T04:44:58Z to 2026-09-30T04:45:14Z
- Variant `no-trailing-user-fix`: The engine as shipped: hooks.py's ensure_trailing_user_turn switched off, so a request that ends on the session-start greeting goes to Claude unchanged.
- Conversations: 2 run, 0 passed, 0 failed, 2 lost to provider errors
- Caller turns: 2; turn latency p50 257.9 ms, p95 387.9 ms, max 387.9 ms
- LLM calls: 2 (1.0 per caller turn, 0 side-channel, 0 empty completions)
- Tokens: 0 prompt (0 cached), 0 completion (of which 0 reasoning)
- Thought signatures sent back: 0 (0 LiteLLM placeholders)
- Bot text sent as 'filler' alongside a tool call: 0; closure_promise: 0; estimate_language: 0
- Case metric quotes_presented: 0 over 0 tool results
- Case metric instructions_sent: 0 over 0 tool results
- Server log events: northgate.payoff_guard 0, northgate.trailing_user_turn_fix 0, mantle.orchestrator.empty_llm_response 0, mantle.turn.failed 2, mantle.memory.discovery.extractor.discover_facts.llm_error 0, mantle.processor.discover_facts.failed 0
- Cost: 0 USD; model calls priced by LiteLLM 1.101.2 from the vendor's published price (https://platform.claude.com/docs/en/about-claude/pricing (Claude Sonnet 5.5: $2 / MTok base input, $2.50 / MTok 5m cache writes, $0.20 / MTok cache hits, $10 / MTok output), checked 2026-09-29), because its bundled map has no row for this model

| Conversation | Kind | Result | Domain tool calls | Turn latency ms | Cost USD |
|---|---|---|---|---|---|
| normal-personal-payoff | normal | ERROR (provider) | none | 388 | 0 |
| adversarial-yesterdays-quote | adversarial | ERROR (provider) | none | 258 | 0 |

## Provider errors

- `normal-personal-payoff`: 1 failed model call(s); not evidence about the agent. See usage.jsonl for the provider message.
- `adversarial-yesterdays-quote`: 1 failed model call(s); not evidence about the agent. See usage.jsonl for the provider message.

Synthetic scenario: Northgate Bank and all its data are fictional. Pass conditions read tool calls, arguments and servicing results from the tracker, never reply wording. closure_promise and estimate_language count bot sentences; case-build/case_metric.py joins payoff figures in bot text to presented quotes for the case metric. None of them decides pass or fail.
