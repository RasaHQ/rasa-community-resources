# Rasa Skills project: Amber Grid home moves (GPT-5.5, text)

This directory is a **Rasa Mantle** agent built for one casebook case,
`utilities-service-move`. Amber Grid is a fictional energy supplier.

Pin: `rasa-pro==3.21.0.dev5`. LLM: `gpt-5.5-2026-04-23` through the `openai`
provider, `reasoning_effort: low`. Channels: `rest`, `socketio`, `inspector`.

## Layout

- `agent.yml`: identity, persona, rules (siblings of `agent:`)
- `integrations.yml`: the GPT-5.5 model group and the channels. Mantle reads
  channels here; it never reads `credentials.yml`
- `memory.yml`: project memory, written by `load_customer_profile` only
- `responses.yml`: the greeting
- `skills/`: `default_session_start`, `service_move` (with the confirmation
  gate on `submit_move_order`), `service_status`
- `tools/amber_grid_moves.py`: `load_customer_profile`, `get_service_status`,
  `check_move_order`, `route_move_review`
- `lib/moves.py`: premises register, move orders, service state, the case
  guard and the tool receipts, no Rasa imports
- `lib/conversation.py`: the customer's messages and the last read-back, from tracker events
- `lib/fixtures/`: fictional data and the vendored case contract
- `hooks.py`: output guard against saying the current supply is already off
- `tests/`: offline guard tests
- `case-build/`: scripted conversations, the case-metric script and recorded live results

## Ground rules

- No tool closes a service. A current service gets an end date only from a
  verified move order, and the end date is the confirmed move-out day.
- The guard lives in `lib/moves.py` and decides at `submit_move_order`. The
  model supplies the customer's words for premises and dates, and a draft id
  copied from a tool result; never a premises id, a date the tools trust, a
  fact, a customer id or an outcome.
- A date is only a day the customer said in the conversation. Keep
  `check_day` refusing vague days ("next month", "the end of October").
- Skill memory (`move_*`) is written only by the tools, one short field per
  value under 100 characters; `tests/test_guard.py` checks every draft the
  fixture allows.
- Any regex over bot text reads straight and typographic apostrophes (GPT-5.5
  writes `’`). Keep the `closure_claim` metric in
  `case-build/conversations.json` identical to `lib/moves.py`; the tests check it.
- `lib/moves.py` refuses fixtures whose organisation is not the casebook's
  fictional supplier (an allowlist, not a list of real names).
- Read fixture files at import time. Mantle imports `lib/` from a temporary
  snapshot that is removed after loading.
- After a change: `make proof-full`, `make validate`, `make train`. A change to
  skills, tools, hooks or `lib/` makes the recorded results stale until the
  conversations are rerun.
