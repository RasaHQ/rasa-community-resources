# retail-guided-selling-gpt-text: run summary

- Case: `retail-guided-selling`; channel: rest; model: `openai/gpt-5.5-2026-04-23` (provider reported gpt-5.5-2026-04-23)
- Run: 2026-09-30T03:05:21Z to 2026-09-30T03:05:54Z
- Variant `reasoning-default`: Rasa's default reasoning_effort for the model (none) instead of low
- Conversations: 3 run, 1 passed, 0 failed, 2 lost to provider errors, 2 skipped for budget
- Caller turns: 3; turn latency p50 3028.0 ms, p95 10238.7 ms, max 10238.7 ms
- LLM calls: 9 (3.0 per caller turn, 1 side-channel, 0 empty completions)
- Tokens: 14398 prompt (4992 cached), 293 completion (of which 0 reasoning)
- Thought signatures sent back: 0 (0 LiteLLM placeholders)
- Bot text sent as 'filler' alongside a tool call: 0; fit_claim: 0
- Server log events: mantle.orchestrator.empty_llm_response 0, mantle.turn.failed 2, mantle.memory.discovery.extractor.discover_facts.llm_error 0
- Cost: 0.058316 USD; model calls priced by LiteLLM 1.101.2 bundled map

| Conversation | Kind | Result | Domain tool calls | Turn latency ms | Cost USD |
|---|---|---|---|---|---|
| normal-dock-lumen7 | normal | pass | record_requirements→recorded, search_catalogue→listed, recommend_product→recommended | 10239 | 0.050291 |
| normal-case-lumen7-pro | normal | ERROR (provider) | none | 3028 | 0.008025 |
| normal-cable-lumen6 | normal | ERROR (provider) | none | 1787 | 0 |

## Provider errors

- `normal-case-lumen7-pro`: 1 failed model call(s); not evidence about the agent. See usage.jsonl for the provider message.
- `normal-cable-lumen6`: 1 failed model call(s); not evidence about the agent. See usage.jsonl for the provider message.

Synthetic scenario: Willow Shop and its catalogue are fictional. Pass conditions read tool calls, arguments and guard outcomes from the tracker; the fit_claim count is read from bot text and reported separately from pass/fail.
