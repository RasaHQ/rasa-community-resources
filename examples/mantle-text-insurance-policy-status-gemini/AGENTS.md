# Rasa Skills project: HarborCover policy status (Gemini, text)

This directory is a **Rasa Mantle** agent built for one casebook case,
`insurance-policy-status`. HarborCover is a fictional insurer.

Pin: `rasa-pro==3.21.0.dev5`. LLM: `gemini-3.1-pro-preview` through the
`gemini` provider (LiteLLM). Channels: `rest`, `socketio`, `inspector`.

## Layout

- `agent.yml`: identity, persona, rules (siblings of `agent:`)
- `integrations.yml`: Gemini model group and the channels. Mantle reads
  channels here; it never reads `credentials.yml`
- `memory.yml`: project memory, written by `load_caller_profile` only
- `responses.yml`: the greeting
- `skills/`: `default_session_start`, `policy_status`, `claim_status`,
  `coverage_question`
- `tools/harborcover_shared.py`: `load_caller_profile`, `open_coverage_question`
- `lib/harborcover.py`: the status service and the case guard, no Rasa imports
- `lib/fixtures/`: fictional data and the vendored case contract
- `hooks.py`: output guard that retries a model response promising cover
- `tests/`: offline guard tests
- `case-build/`: scripted conversations and recorded live results

## Ground rules

- The guard lives in `lib/harborcover.py`. The model supplies only a policy or
  claim number and a loss description; the customer id comes from project
  memory, and the three contract facts are computed from fixture data.
- A coverage outcome only ever comes from a claim record whose
  `decision_type` is `coverage_decision`. Never add a tool that returns one
  from a policy state.
- Read fixture files at import time. Mantle imports `lib/` from a temporary
  snapshot that is removed after loading.
- Keep `lib/fixtures/case-contract.json` identical to the casebook copy;
  `tests/test_guard.py` checks it.
- After a change: `make proof`, `make validate`, `make train`. A change to
  skills, tools, hooks or `lib/` makes the recorded results stale until the
  conversations are rerun.
