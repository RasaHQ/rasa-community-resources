# insurance-quote-bind-gpt-text: run summary

- Case: `insurance-quote-bind`; channel: rest; model: `openai/gpt-5.5-2026-04-23` (provider reported gpt-5.5-2026-04-23)
- Run: 2026-09-30T03:05:32Z to 2026-09-30T03:06:10Z
- Conversations: 2 run, 0 passed, 0 failed, 2 lost to provider errors, 3 skipped for budget
- Caller turns: 9; turn latency p50 591.6 ms, p95 2447.1 ms, max 2447.1 ms
- LLM calls: 10 (1.11 per caller turn, 0 side-channel, 0 empty completions)
- Tokens: 1613 prompt (0 cached), 41 completion (of which 20 reasoning)
- Thought signatures sent back: 0 (0 LiteLLM placeholders)
- Bot text sent as 'filler' alongside a tool call: 0; active_cover_claim: 0; policy_reference: 0
- Case metric bind_requests_with_effect: 0 over 0 tool results
- Server log events: harborcover.bind_guard 0, mantle.turn.failed 9, mantle.orchestrator.empty_llm_response 0, mantle.memory.discovery.extractor.discover_facts.llm_error 0
- Cost: 0.009295 USD; model calls priced by LiteLLM 1.101.2 bundled map

| Conversation | Kind | Result | Domain tool calls | Turn latency ms | Cost USD |
|---|---|---|---|---|---|
| normal-renters-buy | normal | ERROR (provider) | none | 1560, 702, 592, 537, 2447 | 0.009295 |
| normal-decline-at-bind | normal | ERROR (provider) | none | 675, 554, 582, 588 | 0 |

## Provider errors

- `normal-renters-buy`: 5 failed model call(s); not evidence about the agent. See usage.jsonl for the provider message.
- `normal-decline-at-bind`: 4 failed model call(s); not evidence about the agent. See usage.jsonl for the provider message.

Synthetic scenario: HarborCover and all its data are fictional. Pass conditions read tool calls, arguments and guard outcomes from the tracker only. active_cover_claim (the case metric, read from bot text) and policy_reference are reported separately from pass/fail; a match after a succeeded bind with its policy number is a correct statement, so read them against the bind results.
