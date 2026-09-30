# Rasa Skills project: Horizon Rewards redemption (GPT-5.5, text)

This directory is a **Rasa Mantle** agent built for one casebook case,
`travel-redemption`. Horizon Travel and its Horizon Rewards programme are
fictional.

Pin: `rasa-pro==3.21.0.dev5`. LLM: `gpt-5.5-2026-04-23` through the `openai`
provider, `reasoning_effort: low`. Channels: `rest`, `socketio`, `inspector`.

## Layout

- `agent.yml`: identity, persona, rules (siblings of `agent:`)
- `integrations.yml`: GPT-5.5 model group and the channels. Mantle reads
  channels here; it never reads `credentials.yml`
- `memory.yml`: project memory, written by `load_member_profile` only
- `responses.yml`: the greeting
- `skills/`: `default_session_start`, `redeem_reward` (search, hold, release,
  redeem, with the engine's confirmation gate), `rewards_account` (balance,
  earlier redemptions, rewards desk)
- `tools/horizon_shared.py`: `load_member_profile`, `get_points_balance`,
  `get_redemption_status`, `request_rewards_desk_review`
- `lib/horizon.py`: the points ledger, inventory, bookings and the case
  guard, no Rasa imports
- `lib/fixtures/`: fictional data and the vendored case contract
- `tests/`: offline guard tests
- `case-build/`: scripted conversations and recorded live results

## Ground rules

- The guard lives in `lib/horizon.py`. The model supplies an account number
  as the member said it, an option id, a hold id or a redemption reference;
  the member id comes from project memory, and the three contract facts are
  computed from fixture data and session state.
- A redemption is `succeeded` only when the points ledger entry and the
  booking record are read back and match. Never add a path that reports a
  booking from the debit alone.
- The confirmed hold lives in `redeem_reward` skill memory, written only by
  its tools. `redeem_reward` is withheld while no hold is set.
- Read fixture files at import time. Mantle imports `lib/` from a temporary
  snapshot that is removed after loading.
- Keep `lib/fixtures/case-contract.json` identical to the casebook copy;
  `tests/test_guard.py` checks it.
- After a change: `make proof`, `make validate`, `make train`. A change to
  skills, tools or `lib/` makes the recorded results stale until the
  conversations are rerun.
