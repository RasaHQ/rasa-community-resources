# Rasa Skills project: Willow Shop guided selling (GPT-5.5, text)

This directory is a **Rasa Mantle** agent built for one casebook case,
`retail-guided-selling`. Willow Shop is a fictional accessories retailer.

Pin: `rasa-pro==3.21.0.dev5`. LLM: `gpt-5.5-2026-04-23` through the `openai`
provider, `reasoning_effort: low`. Channels: `rest`, `socketio`, `inspector`.

## Layout

- `agent.yml`: identity, persona, rules (siblings of `agent:`)
- `integrations.yml`: the OpenAI model group and the channels. Mantle reads
  channels here; it never reads `credentials.yml`
- `responses.yml`: the greeting
- `skills/`: `default_session_start`, `guided_selling`, `fit_check`
- `tools/willowshop_shared.py`: `record_requirements`, `search_catalogue`,
  `recommend_product`, `request_specialist`
- `lib/willowshop.py`: the catalogue and the case guard, no Rasa imports
- `lib/fixtures/`: fictional data and the vendored case contract
- `tests/`: offline guard tests
- `case-build/`: scripted conversations and recorded live results

## Ground rules

- The guard lives in `lib/willowshop.py`. The model supplies a device model
  name, a product id, a category and a question, never a fact. The device is
  confirmed only when the shopper named it in their own latest message that
  names a device; requirements come from the conversation's last successful
  `record_requirements` result, read from the tracker events.
- Fit comes only from catalogue attributes with a named source. Never add a
  tool that infers fit from a product name or description.
- Keep a known mismatch (`not_compatible`) and an unknown fit
  (`compatibility_unverified`) as different outcomes.
- Read fixture files at import time. Mantle imports `lib/` from a temporary
  snapshot that is removed after loading.
- Keep `lib/fixtures/case-contract.json` identical to the casebook copy;
  `tests/test_guard.py` checks it.
- After a change: `make proof`, `make validate`, `make train`. A change to
  skills, tools or `lib/` makes the recorded results stale until the
  conversations are rerun.
