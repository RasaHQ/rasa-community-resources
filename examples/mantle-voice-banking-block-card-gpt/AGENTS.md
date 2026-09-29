# Rasa Skills project: Northgate block card (GPT-5.5, browser voice)

This directory is a **Rasa Mantle** voice agent built for one casebook case,
`banking-block-card`. Northgate Bank is a fictional bank.

Pin: `rasa-pro==3.21.0.dev5`. LLM: `gpt-5.5-2026-04-23` through the `openai`
provider. Speech: Deepgram Flux (`flux-general-en`) in, Deepgram Aura-2
(`aura-2-andromeda-en`) out. Channels: `browser_audio` (raw WebSocket) and
`inspector`.

## Layout

- `agent.yml`: identity, persona, rules and voice rules (siblings of `agent:`)
- `integrations.yml`: the OpenAI model group and both voice channels. Mantle
  reads channels here; it never reads `credentials.yml`
- `memory.yml`: project memory, written by `verify_caller` only
- `responses.yml`: the greeting
- `skills/block_card/`: the skill, its tools, its confirmation responses and
  the selection memory `select_card` writes
- `lib/northgate.py`: the card service and the case guard, no Rasa imports
- `lib/fixtures/`: fictional data and the vendored case contract
- `tests/`: offline guard tests
- `case-build/`: scripted calls, caller WAV fixtures and recorded live results

## Ground rules

- The guard lives in `lib/northgate.py`. The model supplies a name, a date of
  birth, a card ending and a `card_ref` copied from `select_card`. The
  verified customer id and the selected card are memory only tools write.
- `block_card` has an engine confirmation gate (`tool_constraints` in
  `skill.md`) and blocks only the card `select_card` resolved. Keep both.
- Blocking never orders a replacement. `order_replacement_card` refuses any
  card whose block the service has not read back.
- Read fixture files at import time. Mantle imports `lib/` from a temporary
  snapshot that is removed after loading.
- Keep `lib/fixtures/case-contract.json` identical to the casebook copy.
- Caller WAVs are named from their voice and text. Changing a caller line in
  `case-build/conversations.json` needs `make caller-audio` (billed).
- After a change: `make proof`, `make validate`, `make train`. A change to
  skills, tools or `lib/` makes the recorded results stale until the calls
  are rerun.
