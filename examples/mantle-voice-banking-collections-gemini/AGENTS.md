# Rasa Skills project: Northgate collections (Gemini, browser voice, US Spanish)

This directory is a **Rasa Mantle** voice agent built for one casebook case,
`banking-collections`. Northgate Bank is a fictional bank. The caller and the
agent speak US Spanish.

Pin: `rasa-pro==3.21.0.dev5`. LLM: `gemini-3.8-flash` through the `gemini`
provider (LiteLLM). Speech: Deepgram Flux Multilingual (`flux-general-multi`,
`language_hint=es`) in, Rime Coda (speaker `nieve`, `lang=spa`) out, through
`engines/rime_idle.py`. Channels: `browser_audio` (raw WebSocket) and
`inspector`. Agent language: `es`.

## Layout

- `agent.yml`: identity, persona, rules and voice rules (siblings of `agent:`)
- `integrations.yml`: the Gemini model group and both voice channels. Mantle
  reads channels here; it never reads `credentials.yml`
- `memory.yml`: project memory, written by `load_session_customer` only
- `responses.yml`: the greeting and Spanish versions of Mantle's packaged
  responses
- `engines/rime_idle.py`: Rasa's Rime engine with an idle reconnect, from the
  Northgate advisor-appointment build
- `skills/default_session_start/`: binds the signed-in customer, then greets
- `skills/repayment_plan/`: the skill, its tools (`get_plan_offers`,
  `select_plan_offer`, `record_plan_choice`, `withdraw_plan_choice`,
  `request_hardship_referral`, `request_human_callback`), the read-back
  question and the staged-plan memory
- `tools/northgate_session.py`: `load_session_customer`
- `lib/repayment.py`: offers, the case guard, hardship and withdrawal
  detection, receipts and the fictional-organisation guard, no Rasa imports
- `lib/conversation.py`: the tools' view of the call, from tracker events
- `lib/fixtures/`: fictional data and the vendored case contract
- `tests/`: offline guard and engine tests
- `case-build/`: scripted calls, the caller-audio manifest, three sample WAVs,
  the caller-audio script, the analysis script and recorded live results

## Ground rules

- The guard lives in `lib/repayment.py`. The model supplies an account
  ending, an offer id (or a described plan's installments and amount) and a
  referral summary. The customer id comes from project memory; the three
  contract facts are computed from fixture data and the customer's own words.
- Only permitted plans are recorded: `record_plan_choice` copies the plan
  from the fixture offer, and only when all three rules hold. Never add a
  tool that records a plan from model-supplied amounts or dates.
- Once the customer declares hardship, or a hardship referral is open, no
  tool offers, stages or records a plan for the rest of the call.
- The staged plan is skill memory only the plan tools write. Keep every
  memory value under 100 characters: Mantle cuts longer ones in the prompt.
- Tools send their own receipts (`ToolContext.send`). Keep receipts in
  Spanish and keep "no payment received" in them.
- `lib/repayment.py` refuses fixture data that is not the casebook's
  fictional organisation. The project keeps no list of real names.
- Read fixture files at import time. Mantle imports `lib/` from a temporary
  snapshot that is removed after loading.
- Keep `lib/fixtures/case-contract.json` identical to the casebook copy;
  `tests/test_guard.py` checks it.
- Do not set `utter_on_user_denial` on the confirmation gate: a correction at
  the read-back must be answered in the same turn.
- Caller WAVs are named from their voice and text and kept out of git except
  the three samples. Changing a caller line in `case-build/conversations.json`
  needs `make caller-audio` (billed Gemini TTS or Rime); `make
  check-caller-audio` compares local files with the manifest.
- Do not use OpenAI anywhere in this build (no model, embeddings or caller
  audio).
- After a change: `make proof`, `make validate`, `make train`. A change to
  skills, tools or `lib/` makes the recorded results stale until the calls
  are rerun.
