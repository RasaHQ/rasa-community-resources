# Rasa Skills project: Juniper Mobile connection support (GPT-5.5, text)

This directory is a **Rasa Mantle** agent built for one casebook case,
`telco-diagnostics`. Juniper Mobile is a fictional network operator.

Pin: `rasa-pro==3.21.0.dev5`. LLM: `gpt-5.5-2026-04-23` through the `openai`
provider, `reasoning_effort: low`. Channels: `rest`, `socketio`, `inspector`.

## Layout

- `agent.yml`: identity, persona, rules (siblings of `agent:`)
- `integrations.yml`: GPT-5.5 model group and the channels. Mantle reads
  channels here; it never reads `credentials.yml`
- `memory.yml`: project memory, written by `load_customer_profile` only
- `responses.yml`: the greeting
- `skills/`: `default_session_start`, `outage_status`, `connectivity_recovery`
  (with the recovery tools, the confirmation gate and its responses)
- `tools/juniper_shared.py`: `load_customer_profile`, `check_area_outage`,
  `run_line_diagnostics`, `request_technician_visit` (all read-only)
- `lib/juniper.py`: the network service and the case guard, no Rasa imports
- `lib/fixtures/`: fictional data and the vendored case contract
- `tests/`: offline guard tests
- `case-build/`: scripted conversations and recorded live results

## Ground rules

- The guard lives in `lib/juniper.py`. The model supplies a service id, an
  operation name and a selection reference; the customer id comes from
  project memory, and the three contract facts are computed from the
  per-conversation network state and the engine's transcript.
- `outage_status` has no device tools. Keep it that way.
- A factory reset needs the customer's own words naming it. Never loosen
  `customer_named_destructive` to accept the model's choice.
- Read fixture files at import time. Mantle imports `lib/` from a temporary
  snapshot that is removed after loading.
- Keep `lib/fixtures/case-contract.json` identical to the casebook copy;
  `tests/test_guard.py` checks it.
- After a change: `make proof`, `make validate`, `make train`. A change to
  skills, tools or `lib/` makes the recorded results stale until the
  conversations are rerun.
