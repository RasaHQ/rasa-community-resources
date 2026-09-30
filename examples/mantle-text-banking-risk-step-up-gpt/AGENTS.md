# Rasa Skills project: Northgate risk step-up (GPT-5.5, text)

This directory is a **Rasa Mantle** agent built for one casebook case,
`banking-risk-step-up`. Northgate Bank is a fictional bank.

Pin: `rasa-pro==3.21.0.dev5`. LLM: `gpt-5.5-2026-04-23` through the `openai`
provider, `reasoning_effort: low`. Channels: `rest`, `socketio`, `inspector`.

## Layout

- `agent.yml`: identity, persona, rules (siblings of `agent:`)
- `integrations.yml`: the GPT-5.5 model group and the channels. Mantle reads
  channels here; it never reads `credentials.yml`
- `memory.yml`: project memory, written by `load_caller_profile` only
- `responses.yml`: the greeting
- `skills/`: `default_session_start`, `balance_enquiry`, `transfer_money`
- `tools/northgate_shared.py`: `load_caller_profile`, `get_balance`
- `lib/northgate.py`: the payments service and the step-up guard, no Rasa imports
- `lib/fixtures/`: fictional data and the vendored case contract
- `tests/`: offline guard tests
- `case-build/`: scripted conversations and recorded live results

## Ground rules

- The guard lives in `lib/northgate.py` and runs inside `submit_transfer`.
  The model supplies an account, a destination, an amount, a reference copied
  from a tool result and the code the customer typed. The customer id comes
  from project memory; risk levels and the three contract facts are computed
  from fixture data and per-conversation state.
- A verification counts only for the assessment it was issued for. Never add
  a path that lets a session, or a code verified for another transfer,
  authorise a transfer that needs more.
- Every new assessment supersedes the open ones and voids their codes and
  verifications. Keep it that way: it is the case's correction rule.
- Read fixture files at import time. Mantle imports `lib/` from a temporary
  snapshot that is removed after loading.
- Keep `lib/fixtures/case-contract.json` identical to the casebook copy;
  `tests/test_guard.py` checks it.
- After a change: `make proof`, `make validate`, `make train`. A change to
  skills, tools or `lib/` makes the recorded results stale until the
  conversations are rerun.
