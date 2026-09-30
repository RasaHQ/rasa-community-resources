# Rasa Skills project: Cedar Clinic pre-visit intake (Gemini, text)

This directory is a **Rasa Mantle** agent built for one casebook case,
`healthcare-intake`. Cedar Clinic is a fictional clinic, and the two payers
are invented.

Pin: `rasa-pro==3.21.0.dev5`. LLM: `gemini-3.1-pro-preview` through the
`gemini` provider (LiteLLM), no reasoning setting. Channels: `rest`,
`socketio`, `inspector`. Scope: administrative intake only, no clinical
advice.

## Layout

- `agent.yml`: identity, persona, rules (siblings of `agent:`)
- `integrations.yml`: the Gemini model group and the channels. Mantle reads
  channels here; it never reads `credentials.yml`
- `memory.yml`: project memory, written by `load_session_patient` only
- `responses.yml`: the greeting
- `skills/default_session_start/`: binds the signed-in patient, then greets
- `skills/pre_visit_intake/`: the skill, its tools, the read-back question and
  the intake memory its tools write
- `skills/clinical_question/`: routes clinical questions, never answers them
- `tools/cedar_intake.py`: `load_session_patient`, `refer_clinical_question`
- `lib/intake.py`: registration record, eligibility service, access desk,
  the case guard and the receipts, no Rasa imports
- `lib/conversation.py`: reads the last read-back and its answer from
  tracker events
- `lib/fixtures/`: fictional data and the vendored case contract
- `tests/`: offline guard, receipt and memory tests
- `case-build/`: scripted conversations, the case-metric script and recorded
  live results

## Ground rules

- The guard lives in `lib/intake.py`. The model supplies a phone number, a
  payer name, a member id, a policyholder, an intake id and a one-line
  question, never a fact, a response code or an outcome.
- Response codes come from the fixture eligibility service and have labels in
  `RESPONSE_CODES`. A new payer or member id invalidates the earlier lookup
  and its follow-up.
- `record_intake` is hidden from the model until the payer response is
  labelled and any open question has an owner (`requires` on
  `intake_ready_to_record`), has an engine confirmation gate that reads the
  intake back with its version tag, and checks all three contract facts
  itself. It sets no `utter_on_user_denial`, so a correction at the read-back
  is answered in the same turn.
- `payment_guarantee` is always `None`. No tool may return a coverage or
  payment answer.
- `TOOL_SENDS_RECEIPT = True` in `lib/intake.py`: `record_intake` and
  `assign_access_followup` send the patient their own receipt through
  `ToolContext.send`.
- Each memory value is one short field under 100 characters. Mantle cuts
  longer values in the prompt without a log line; `tests/test_guard.py`
  checks every fixture combination.
- The fixture's organisation must be the casebook contract's own fictional
  clinic, and every other organisation field one of the two allowlisted
  invented payers, each marked `(fictional ...)`; the library refuses to load
  otherwise. Never add real institution names, in fixtures or tests.
- Read fixture files at import time. Mantle imports `lib/` from a temporary
  snapshot that is removed after loading.
- Keep `lib/fixtures/case-contract.json` identical to the casebook copy.
- After a change: `make proof`, `make validate`, `make train`. A change to
  skills, tools or `lib/` makes the recorded results stale until the
  conversations are rerun. Live runs use `gemini-3.1-pro-preview`, whose
  project quota is 250 requests a day; a full run makes about 150.
