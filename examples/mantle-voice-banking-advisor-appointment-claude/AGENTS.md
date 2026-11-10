# Rasa Skills project: Northgate advisor appointments (Claude, browser voice)

This directory is a **Rasa Mantle** voice agent built for one casebook case,
`banking-advisor-appointment`. Northgate Bank is a fictional UK bank; its
branches, teams, customer and diary are invented.

Pin: `rasa-pro==3.21.0.dev5`. LLM: `claude-sonnet-5-5` through the
`anthropic` provider (LiteLLM). Speech: Deepgram Flux (`flux-general-en`) in,
Rime Coda (speaker `vashti`) out. Channels: `browser_audio` (raw WebSocket)
and `inspector`.

## Layout

- `agent.yml`: identity, persona, rules and voice rules (siblings of `agent:`)
- `integrations.yml`: the Claude model group and both voice channels. Mantle
  reads channels here; it never reads `credentials.yml`
- `memory.yml`: project memory, written by `load_session_customer` only
- `responses.yml`: the greeting
- `skills/default_session_start/`: binds the signed-in customer, then greets
- `skills/book_advisor_appointment/`: the skill, its tools
  (`find_advisor_slots`, `hold_slot`, `release_hold`, `book_appointment`,
  `request_callback`), the confirmation question and the held-slot memory
- `tools/northgate_session.py`: `load_session_customer`
- `lib/appointments.py`: the diary, the case guard and the
  fictional-organisation guard, no Rasa imports
- `lib/fixtures/`: fictional data and the vendored case contract
- `tests/`: offline guard tests
- `case-build/`: scripted calls, the caller-audio manifest, three sample WAVs,
  the caller-audio regeneration script and recorded live results

## Ground rules

- The guard lives in `lib/appointments.py`. The customer's purpose, meeting
  channel and step-free need come from their own messages in the tracker; the
  model's purpose word must agree with them. The customer id comes from
  project memory, and the held slot from skill memory only the tools write.
- Never add a tool that books without a hold, or a path that books a general
  appointment for a specialist purpose.
- `lib/appointments.py` refuses fixture data whose organisation is not exactly
  the casebook contract's organisation marked `(fictional)`. Keep no list of
  real institution names anywhere in this project: the repository's
  fictional-data lint rejects them in every tracked file.
- Read fixture files at import time. Mantle imports `lib/` from a temporary
  snapshot that is removed after loading.
- Keep `lib/fixtures/case-contract.json` identical to the casebook copy;
  `tests/test_guard.py` checks it.
- Keep every memory value under 100 characters: Mantle cuts longer values in
  the prompt without saying so.
- Caller WAVs are named from their voice and text and kept out of git except
  the three samples. Changing a caller line in `case-build/conversations.json`
  needs `make caller-audio` (billed Gemini TTS); `make check-caller-audio`
  compares local files with the manifest.
- Do not use OpenAI anywhere in this build (no model, embeddings or caller
  audio): the build was made without OpenAI credit, and its receipts say so.
- After a change: `make proof`, `make validate`, `make train`. A change to
  skills, tools or `lib/` makes the recorded results stale until the calls
  are rerun.
