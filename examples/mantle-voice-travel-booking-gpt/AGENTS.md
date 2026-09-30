# Rasa Skills project: Horizon Travel journey changes (GPT, browser voice)

This directory is a **Rasa Mantle** voice agent built for one casebook case,
`travel-booking`. Horizon Travel is a fictional travel company; its partners,
traveller, bookings, flights and references are invented.

Pin: `rasa-pro==3.21.0.dev5`. LLM: `gpt-5.5-2026-04-23` through the `openai`
provider (LiteLLM), `reasoning_effort: low`. Speech: Deepgram Flux
(`flux-general-en`) in, through Rasa's built-in `deepgram` engine; Rime
Mist v3 (speaker `peak`) out, through `engines/rime_idle.py`. Channels:
`browser_audio` (raw WebSocket) and `inspector`.

## Layout

- `agent.yml`: identity, persona, rules, voice rules and `tool_timeout: 30`
  (siblings of `agent:`)
- `integrations.yml`: the GPT model group and both voice channels. Mantle
  reads channels here; it never reads `credentials.yml`
- `memory.yml`: project memory, written by `load_session_traveller` only
- `responses.yml`: the greeting
- `engines/rime_idle.py`: Rasa's Rime engine, reopening its socket after 20 s
  idle (from the Northgate advisor build)
- `skills/default_session_start/`: binds the signed-in traveller, then greets
- `skills/change_travel_booking/`: the skill, its tools (`look_up_trip`,
  `check_flight_status`, `find_change_options`, `prepare_journey_change`,
  `apply_journey_change`, `discard_journey_change`), the confirmation
  question and the draft-change memory
- `tools/horizon_session.py`: `load_session_traveller`
- `lib/journeys.py`: bookings, the journey plan, the case guard, the
  reconciliation, the receipts and the fictional-organisation guard, no Rasa
  imports
- `lib/fixtures/`: fictional data and the vendored case contract
- `tests/`: offline guard, journey, receipt and engine tests
- `case-build/`: scripted calls, the caller-audio manifest, the caller-audio
  script, the analysis script and recorded live results

## Ground rules

- There is no flight-only change. `apply_journey_change` checks every linked
  service, changes the segment, moves the services and reconciles them;
  `tests/test_journeys.py` fails if a flight-only tool appears.
- The guard lives in `lib/journeys.py`. Do not relax a rule to make a call
  pass: a draft that no longer matches the segment is `wrong_segment`, an
  unreadable partner is `connection_not_checked`, and a service that still
  points at the old times leaves the change `pending` and the booking frozen.
- `lib/journeys.py` refuses fixture data whose organisation is not exactly the
  casebook contract's organisation marked `(fictional)`. Keep no list of real
  institution names anywhere in this project: the repository's
  fictional-data lint rejects them in every tracked file.
- Read fixture files at import time. Mantle imports `lib/` from a temporary
  snapshot that is removed after loading.
- Keep `lib/fixtures/case-contract.json` identical to the casebook copy;
  `tests/test_journeys.py` checks it.
- Keep every memory value under 100 characters: Mantle cuts longer values in
  the prompt without saying so. A test checks every option of every booking.
- Match straight and curly apostrophes in every pattern.
- Leave `utter_on_user_denial` unset: with one, a correction at the
  confirmation question gets only the canned line.
- Keep the change receipt short: on voice the tool waits while it is spoken,
  and the wait counts against `tool_timeout`.
- Caller WAVs are named from their voice and text and kept out of git except
  the samples. Changing a caller line in `case-build/conversations.json` needs
  `make caller-audio` (billed); `make check-caller-audio` compares local files
  with the manifest.
- After a change: `make proof`, `make validate`, `make train`. A change to
  skills, tools, engines or `lib/` makes the recorded results stale until the
  calls are rerun.
