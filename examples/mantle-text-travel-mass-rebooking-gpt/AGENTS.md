# Rasa Skills project: Horizon Travel storm rebooking (GPT-5.5, text)

This directory is a **Rasa Mantle** agent built for one casebook case,
`travel-mass-rebooking`. Horizon Travel and everything in its fixtures are
fictional.

Pin: `rasa-pro==3.21.0.dev5`. LLM: `gpt-5.5-2026-04-23` through the `openai`
provider, `reasoning_effort: low`. Channels: `rest`, `socketio`, `inspector`.

## Layout

- `agent.yml`: identity, persona, rules (siblings of `agent:`)
- `integrations.yml`: GPT-5.5 model group and the channels. Mantle reads
  channels here; it never reads `credentials.yml`
- `memory.yml`: project memory, written by `load_passenger_profile` only
- `responses.yml`: the greeting
- `skills/`: `default_session_start`, `rebook_itinerary` (search, hold,
  resume, release, commit, with the engine's confirmation gate),
  `disruption_case` (case state, pending commits, recovery desk)
- `tools/horizon_disruption.py`: `load_passenger_profile`,
  `get_disruption_case`, `check_rebooking_status`, `request_recovery_desk`
- `lib/rebooking.py`: cases, inventory, holds, the booking service, the fixture
  clock, the case guard and the receipts, no Rasa imports
- `lib/fixtures/`: fictional data and the vendored case contract
- `tests/`: offline guard tests
- `case-build/`: scripted conversations, the case-metric script and recorded
  live results

## Ground rules

- The guard lives in `lib/rebooking.py`. The model supplies a case reference,
  an option id, a hold id, a commit reference, an accessible-connection flag
  and a reason; the passenger id comes from project memory, and the three
  contract facts are computed from fixture data, the fixture clock, session
  state and the passenger's own messages.
- An offer, a hold and a committed replacement are different statuses. A
  rebooking is `succeeded` only when the booking service's ticket record is
  read back and matches the hold. Never add a path that reports a rebooking
  from a hold or a commit request alone.
- An expired hold is never reused. Requirements are only added in chat, never
  removed; case constraints change only through the recovery desk.
- The confirmed hold lives in `rebook_itinerary` skill memory, written only by
  its tools, one short field per value (Mantle cuts a memory value at 100
  characters; `tests/test_guard.py` checks every fixture). `commit_rebooking`
  is withheld while no hold is set.
- Leave `utter_on_user_denial` unset, so a correction given at the
  confirmation is answered in the same turn.
- The tools send the passenger's receipt themselves (`TOOL_SENDS_RECEIPT`).
- The fixture organisation guard is an allowlist of the contract's own
  company. Do not add a list of real names; `scripts/lint_repo.py` owns that.
- Read fixture files at import time. Mantle imports `lib/` from a temporary
  snapshot that is removed after loading.
- Keep `lib/fixtures/case-contract.json` identical to the casebook copy;
  `tests/test_guard.py` checks it.
- After a change: `make proof`, `make validate`, `make train`. A change to
  skills, tools or `lib/` makes the recorded results stale until the
  conversations are rerun.
