# Rasa Skills project: HarborCover quote and bind (GPT-5.5, text)

This directory is a **Rasa Mantle** agent built for one casebook case,
`insurance-quote-bind`. HarborCover is a fictional insurer.

Pin: `rasa-pro==3.21.0.dev5`. LLM: `gpt-5.5-2026-04-23` through the `openai`
provider, `reasoning_effort: low`. Channels: `rest`, `socketio`, `inspector`.

## Layout

- `agent.yml`: identity, persona, rules (siblings of `agent:`)
- `integrations.yml`: GPT-5.5 model group and the channels. Mantle reads
  channels here; it never reads `credentials.yml`
- `memory.yml`: project memory, written once by `load_caller_profile`
- `responses.yml`: the greeting
- `skills/quote_bind/`: the skill, its tools, the two engine confirmations
  (`responses.yml`) and the skill memory they read back (`memory.yml`)
- `tools/harborcover_quotes_shared.py`: `load_caller_profile`
- `lib/quotes.py`: quote, underwriting and binding services and the case
  guard, no Rasa imports
- `lib/fixtures/`: fictional data and the vendored case contract
- `hooks.py`: output guard against active-cover wording and unverified
  policy numbers
- `tests/`: offline guard tests
- `case-build/`: scripted conversations and recorded live results

## Ground rules

- The guard lives in `lib/quotes.py`. The model supplies a quote id, an offer
  id, a question id and the customer's answer; the customer id comes from
  project memory, and the three contract facts are computed from service
  state.
- A policy number only ever comes from a binding receipt that matches the
  offer id, version and answers hash. Never add a tool that returns one from
  an estimate, an offer or a payment.
- Every tool that reads or changes answers or offers rewrites the skill memory
  the confirmations read back (`_remember` in `skills/quote_bind/tools.py`).
- Project memory is write-once; skill memory is not.
- A confirmed gated tool reaches `modify_tool_result` as
  `resolve_tool_confirmation`, not under its own name. See `hooks.py`.
- Read fixture files at import time. Mantle imports `lib/` from a temporary
  snapshot that is removed after loading.
- Keep `lib/fixtures/case-contract.json` identical to the casebook copy;
  `tests/test_guard.py` checks it.
- After a change: `make proof`, `make validate`, `make train`. A change to
  skills, tools, hooks or `lib/` makes the recorded results stale until the
  conversations are rerun.
