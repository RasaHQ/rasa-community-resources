# Rasa Skills project: Northgate dispute intake (Claude Sonnet 5.5, browser voice)

This directory is a **Rasa Mantle** voice agent built for one casebook case,
`banking-dispute`. Northgate Bank is a fictional bank.

Pin: `rasa-pro==3.21.0.dev5`. LLM: `claude-sonnet-5-5` through the `anthropic`
provider. Speech: Speechmatics realtime (`enhanced`, through the companion's
`voicerouter.providers.speechmatics.SpeechmaticsASR`, not `RoutedASR`) in,
Rime Mist v3 (`ironwood`) out. Channels: `browser_audio` (raw WebSocket) and
`inspector`.

## Layout

- `agent.yml`: identity, persona, rules and voice rules (siblings of `agent:`)
- `integrations.yml`: the Anthropic model group and both voice channels. Mantle
  reads channels here; it never reads `credentials.yml`
- `pyproject.toml`: pins rasa-pro and installs `patterns/voice-vendor-router`
  as a path dependency, so the Speechmatics engine imports by dotted path
- `memory.yml`: project memory, written by `verify_caller` only
- `responses.yml`: the greeting
- `skills/open_dispute/`: the skill, its tools, its confirmation responses and
  the selection memory `select_transaction` writes
- `lib/disputes.py`: the ledger, the case service and the case guard, no Rasa
  imports
- `lib/fixtures/`: fictional data and the vendored case contract
- `tests/`: offline guard tests
- `case-build/`: scripted calls, caller WAV fixtures and recorded live results

## Ground rules

- The guard lives in `lib/disputes.py`. The model supplies a name, a date of
  birth, a description of the charge, a `transaction_ref` copied from
  `select_transaction` and the caller's statement. The verified customer and
  the selected transaction are memory only tools write.
- `file_dispute` has an engine confirmation gate (`tool_constraints` in
  `skill.md`) that reads the contract's question back, and files only the
  transaction `select_transaction` resolved. Keep both.
- A receipt never carries a reimbursement outcome. `reimbursement_decision`
  and `provisional_credit` are always `None`. Card blocking is a separate tool
  with its own reference.
- Read fixture files at import time. Mantle imports `lib/` from a temporary
  snapshot that is removed after loading.
- Keep `lib/fixtures/case-contract.json` identical to the casebook copy.
- Caller WAVs are named from their voice and text. Changing a caller line in
  `case-build/conversations.json` needs `make caller-audio` (billed).
- After a change: `make proof`, `make validate`, `make train`. A change to
  skills, tools, `lib/` or the speech settings makes the recorded results
  stale until the calls are rerun.
