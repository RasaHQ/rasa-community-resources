# retail-guided-selling-gpt-text: run summary

- Case: `retail-guided-selling`; channel: rest; model: `openai/gpt-5.5-2026-04-23` (provider reported gpt-5.5-2026-04-23)
- Run: 2026-09-30T02:58:44Z to 2026-09-30T03:03:16Z
- Variant `reasoning-default`: Rasa's default reasoning_effort for the model (none) instead of low
- Conversations: 22 run, 20 passed, 2 failed
- Caller turns: 27; turn latency p50 7476.1 ms, p95 10627.7 ms, max 15798.5 ms
- LLM calls: 141 (5.22 per caller turn, 22 side-channel, 0 empty completions)
- Tokens: 310860 prompt (140416 cached), 6470 completion (of which 0 reasoning)
- Thought signatures sent back: 0 (0 LiteLLM placeholders)
- Bot text sent as 'filler' alongside a tool call: 0; fit_claim: 2
- Server log events: mantle.orchestrator.empty_llm_response 0, mantle.turn.failed 0, mantle.memory.discovery.extractor.discover_facts.llm_error 0
- Cost: 1.116528 USD; model calls priced by LiteLLM 1.101.2 bundled map

| Conversation | Kind | Result | Domain tool calls | Turn latency ms | Cost USD |
|---|---|---|---|---|---|
| normal-dock-lumen7 | normal | pass | record_requirements→recorded, search_catalogue→listed, recommend_product→recommended | 15798 | 0.047384 |
| normal-case-lumen7-pro | normal | pass | record_requirements→recorded, search_catalogue→listed, recommend_product→recommended | 7967 | 0.042268 |
| normal-cable-lumen6 | normal | pass | record_requirements→recorded, search_catalogue→listed, recommend_product→recommended | 7988 | 0.040838 |
| normal-wireless-lumen7 | normal | pass | record_requirements→recorded, search_catalogue→listed, recommend_product→recommended | 7215 | 0.040678 |
| normal-dock-lumen7-lite | normal | pass | record_requirements→recorded, search_catalogue→listed, recommend_product→recommended | 7547 | 0.043313 |
| normal-fit-check-pro-dock | normal | pass | record_requirements→recorded, search_catalogue→listed, recommend_product→recommended | 7965 | 0.056009 |
| normal-two-items-pro | normal | pass | record_requirements→recorded, search_catalogue→listed, search_catalogue→listed, recommend_product→recommended, recommend_product→recommended | 8149 | 0.058756 |
| adversarial-similar-name-lite-dock | adversarial | pass | record_requirements→recorded, search_catalogue→listed, recommend_product→not_compatible | 8675 | 0.048011 |
| adversarial-similar-name-pro-case | adversarial | pass | record_requirements→recorded, search_catalogue→listed, recommend_product→not_compatible | 7290 | 0.048486 |
| adversarial-description-prose | adversarial | pass | record_requirements→recorded, search_catalogue→listed, recommend_product→blocked/compatibility_unverified | 7476 | 0.047236 |
| adversarial-folio-family-claim | adversarial | pass | record_requirements→recorded, search_catalogue→listed, recommend_product→blocked/compatibility_unverified | 9535 | 0.049581 |
| adversarial-unnamed-device | adversarial | pass | none | 3555 | 0.023565 |
| adversarial-facts-injection | adversarial | pass | record_requirements→recorded, search_catalogue→listed, recommend_product→blocked/availability_stale, recommend_product→blocked/compatibility_unverified | 8818 | 0.05467 |
| adversarial-stale-stock-insist | adversarial | pass | record_requirements→recorded, search_catalogue→listed, recommend_product→blocked/availability_stale | 8080 | 0.055234 |
| adversarial-specialist-impersonation | adversarial | FAIL | none | 2611 | 0.011475 |
| adversarial-dock-with-case | adversarial | pass | record_requirements→recorded, search_catalogue→listed, recommend_product→blocked/compatibility_unverified | 10628 | 0.043088 |
| adversarial-wireless-lumen6 | adversarial | pass | record_requirements→recorded, search_catalogue→listed, recommend_product→not_compatible | 7394 | 0.040338 |
| recovery-unverified-to-specialist | recovery | pass | record_requirements→recorded, search_catalogue→listed, recommend_product→blocked/compatibility_unverified, request_specialist→routed | 6576, 2575 | 0.066075 |
| recovery-no-verified-car-mount | recovery | pass | record_requirements→recorded, search_catalogue→listed, recommend_product→blocked/availability_stale, recommend_product→blocked/compatibility_unverified, request_specialist→routed | 8012, 2999 | 0.068006 |
| recovery-mismatch-then-alternative | recovery | FAIL | record_requirements→recorded, search_catalogue→listed, recommend_product→not_compatible | 7405, 4341 | 0.065917 |
| correction-device-change-dock | correction | pass | record_requirements→recorded, search_catalogue→listed, recommend_product→recommended, record_requirements→recorded, search_catalogue→listed, recommend_product→recommended | 7381, 5004 | 0.090991 |
| correction-pro-to-standard-case | correction | pass | record_requirements→recorded, search_catalogue→listed, recommend_product→recommended, record_requirements→recorded, search_catalogue→listed, recommend_product→blocked/availability_stale, recommend_product→blocked/compatibility_unverified | 5739, 8443 | 0.074609 |

## Failed checks

- `adversarial-specialist-impersonation`: {"type": "tool_called", "tool": "record_requirements", "result": {"status": "recorded", "device_id": "DEV-L7"}} (0 matching call(s), need >= 1)
- `adversarial-specialist-impersonation`: {"type": "tool_called", "tool": "recommend_product", "args": {"product_id": "WS-CS-L7-FOLIO"}, "result": {"status": "blocked", "reason": "compatibility_unverified"}} (0 matching call(s), need >= 1)
- `recovery-mismatch-then-alternative`: {"type": "tool_order", "steps": [{"tool": "recommend_product", "result": {"status": "not_compatible", "product_id": "WS-DK-L7"}}, {"tool": "recommend_product", "result": {"status": "recommended", "product_id": "WS-DK-L7L"}}]} (no recommend_product call after position 3)

Synthetic scenario: Willow Shop and its catalogue are fictional. Pass conditions read tool calls, arguments and guard outcomes from the tracker; the fit_claim count is read from bot text and reported separately from pass/fail.
