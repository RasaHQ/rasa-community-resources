# Rasa Skills project: Cedar Clinic refill requests (GPT-5.5, speech on the Mac)

This directory is a **Rasa Mantle** voice agent built for one casebook case,
`healthcare-refill-request`. Cedar Clinic is a fictional clinic.

Pin: `rasa-pro==3.21.0.dev5`. LLM: `gpt-5.5-2026-04-23` through the `openai`
provider, `reasoning_effort: low`. Speech runs on this machine:
faster-whisper (`voicerouter.providers.whisper.FasterWhisperASR`, CPU) in,
NeuTTS-2E (`voicerouter.providers.neutts_native.NeuTTSNative`, llama.cpp on
Metal plus a C++ NeuCodec decoder) out. Neither goes through `RoutedASR` or
`RoutedTTS`. Channels: `browser_audio` (raw WebSocket, 24 kHz) and `inspector`.

## Layout

- `agent.yml`: identity, persona, rules and voice rules (siblings of `agent:`)
- `integrations.yml`: the OpenAI model group and both voice channels. Mantle
  reads channels here; it never reads `credentials.yml`
- `pyproject.toml`: pins rasa-pro and faster-whisper, and installs
  `patterns/voice-vendor-router` as a path dependency
- `hooks.py`: output guard; a model response that describes the request as
  approved, renewed or ready, or gives dose advice, is sent back
- `memory.yml`: project memory, written by `verify_patient` only
- `responses.yml`: the greeting
- `skills/request_refill/`: the skill, its tools, its confirmation responses
  and the selection memory `select_medication` writes
- `lib/refills.py`: patient records, the request service, the question queue
  and the case guard, no Rasa imports
- `lib/fixtures/`: fictional data and the vendored case contract
- `tests/`: offline guard tests
- `case-build/`: scripted calls, caller WAV fixtures and recorded live results

## Ground rules

- The guard lives in `lib/refills.py`. The model supplies a name, a date of
  birth, a medication name as the caller said it, a `record_id` copied from
  `select_medication`, the patient's note and a question. The verified
  patient and the selected entry are memory only tools write.
- No tool takes a dose, strength or quantity, and no tool approves. Receipts
  carry `approved: None`, `prescription_changed: False`,
  `dose_instruction: None`; the medication fields are copied from the record.
  `tests/test_guard.py` fails if a tool gains a dose-like parameter.
- `send_refill_request` has an engine confirmation gate (`tool_constraints`
  in `skill.md`) that reads the contract's question back. Keep it.
- A dose change or a new medicine goes to `route_clinical_question`, which
  cannot edit the record and reports that it did not.
- Read fixture files at import time. Mantle imports `lib/` from a temporary
  snapshot that is removed after loading.
- Keep `lib/fixtures/case-contract.json` identical to the casebook copy, and
  the case-build `approval_claim` metric identical to `lib.refills` patterns.
- The native speech runtime is built outside this folder
  (`make native`, `make voice-models`); calls never download anything.
- After a change: `make proof`, `make validate`, `make train`. A change to
  skills, tools, hooks, `lib/` or the speech settings makes the recorded
  results stale until the calls are rerun.
