# Rasa Skills project: Horizon Travel disruption mode (GPT-5.5, text)

This directory is a **Rasa Mantle** agent built for one casebook case,
`disruption-mode`. Horizon Travel is a fictional travel company.

Pin: `rasa-pro==3.21.0.dev5`. LLM: `gpt-5.5-2026-04-23` through the `openai`
provider, `reasoning_effort: low`. Channels: `rest`, `socketio`, `inspector`.

## Layout

- `agent.yml`: identity, persona, rules (siblings of `agent:`)
- `integrations.yml`: the GPT-5.5 model group and the channels. Mantle reads
  channels here; it never reads `credentials.yml`
- `memory.yml`: project memory, written by `load_session_passenger` only
- `responses.yml`: the greeting
- `skills/`: `default_session_start`, `disruption_recovery` (with the
  confirmation gate on `hold_recovery_option`), `disruption_status`
- `tools/horizon_shared.py`: `load_session_passenger`, `get_incident_status`,
  `check_hold`, `release_hold`, `join_recovery_queue`
- `lib/recovery.py`: the incident, inventory, holds, queue, the case guard,
  the receipts and the promise patterns, no Rasa imports
- `lib/fixtures/`: fictional data and the vendored case contract
- `hooks.py`: output guard against unbacked recovery promises
- `tests/`: offline guard, receipt, memory and hook tests
- `case-build/`: scripted conversations, the case-metric script and recorded live results

## Ground rules

- The guard lives in `lib/recovery.py` and decides at `hold_recovery_option`,
  from the incident, inventory and booking state then. The model supplies the
  passenger's words for a booking and an option id or hold id copied from a
  tool result; never a fact, a seat count, a revision or a passenger id.
- Nothing in this chat confirms a journey. Never add a path that reports a
  hold or a queue entry as a booking.
- Skill memory (`selected_option_id`, `selected_booking_ref`,
  `selected_option_summary`) is written only by the tools. A new search
  clears the selection. Each memory value is one short field under 100
  characters (Mantle cuts longer ones silently); `tests/test_guard.py` checks.
- The tools send the passenger their own receipt (`ToolContext.send`); keep
  `lib.recovery.customer_receipt` free of promise sentences.
- Leave `utter_on_user_denial` unset on the hold gate, so a correction at the
  confirmation question is answered in the same turn.
- Read fixture files at import time. Mantle imports `lib/` from a temporary
  snapshot that is removed after loading. The fixture must pass the
  organisation allowlist in `lib/recovery.py`.
- Keep `lib/fixtures/case-contract.json` identical to the casebook copy, and
  the `commitment_promise` and `hold_claim` metrics in
  `case-build/conversations.json` identical to `lib/recovery.py`;
  `tests/test_guard.py` checks both.
- After a change: `make proof-full`, `make validate`, `make train`. A change to
  skills, tools, hooks or `lib/` makes the recorded results stale until the
  conversations are rerun.
