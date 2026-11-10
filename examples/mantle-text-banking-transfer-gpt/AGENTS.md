# Rasa Skills project: Northgate Bank transfers (GPT-5.5, text)

This directory is a **Rasa Mantle** agent built for one casebook case,
`banking-transfer`. Northgate Bank is a fictional bank.

Pin: `rasa-pro==3.21.0.dev5`. LLM: `gpt-5.5-2026-04-23` through the `openai`
provider, `reasoning_effort: low`. Channels: `rest`, `socketio`, `inspector`.

## Layout

- `agent.yml`: identity, persona, rules (siblings of `agent:`)
- `integrations.yml`: the GPT-5.5 model group and the channels. Mantle reads
  channels here; it never reads `credentials.yml`
- `memory.yml`: project memory, written by `load_caller_profile` only
- `responses.yml`: the greeting
- `skills/`: `default_session_start`, `transfer_money` (with the confirmation
  gate on `submit_transfer`), `transfer_status`, `account_balance`
- `tools/northgate_shared.py`: `load_caller_profile`, `get_balance`,
  `check_transfer_status`, `escalate_reconciliation`
- `lib/ledger.py`: the ledger, the payee resolver and the case guard, no Rasa imports
- `lib/fixtures/`: fictional data and the vendored case contract
- `hooks.py`: output guard against describing an unposted transfer as posted
- `tests/`: offline guard tests
- `case-build/`: scripted conversations, the case-metric script and recorded live results

## Ground rules

- The guard lives in `lib/ledger.py` and decides at `submit_transfer`, from
  the ledger's state then. The model supplies the caller's words, an amount,
  and a `payee_ref` or `draft_id` copied from a tool result; never a balance,
  a fact, a customer id or a payee account number.
- Only a transfer between the customer's own accounts posts at once. Never
  add a path that reports a saved-payee transfer as posted from a submission.
- Skill memory (`selected_payee_ref`, `draft_id`, `draft_summary`) is written
  only by the tools. A new payee selection clears the draft.
- Read fixture files at import time. Mantle imports `lib/` from a temporary
  snapshot that is removed after loading.
- Keep `lib/fixtures/case-contract.json` identical to the casebook copy, and
  the `posted_claim` metric in `case-build/conversations.json` identical to
  `lib/ledger.py`; `tests/test_guard.py` checks both.
- After a change: `make proof-full`, `make validate`, `make train`. A change to
  skills, tools, hooks or `lib/` makes the recorded results stale until the
  conversations are rerun.
