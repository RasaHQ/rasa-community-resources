# Rasa Skills project: Willow Shop order payments (GPT, browser voice)

This directory is a **Rasa Mantle** voice agent built for one casebook case,
`voice-payment-boundary`. Willow Shop is a fictional retailer; its payment
processor, customer, orders and contact details are invented.

Pin: `rasa-pro==3.21.0.dev5`. LLM: `gpt-5.5-2026-04-23` through the `openai`
provider (LiteLLM), `reasoning_effort: low`. Speech: Deepgram Flux
(`flux-general-en`) in, through `engines/deepgram_pci.py`; Rime Mist v3
(speaker `lagoon`) out, through `engines/rime_idle.py`. Channels:
`browser_audio` (raw WebSocket) and `inspector`.

## Layout

- `agent.yml`: identity, persona, rules, voice rules and `tool_timeout: 30`
  (siblings of `agent:`)
- `integrations.yml`: the GPT model group and both voice channels. Mantle
  reads channels here; it never reads `credentials.yml`
- `memory.yml`: project memory, written by `load_session_customer` only
- `responses.yml`: the greeting
- `engines/deepgram_pci.py`: Rasa's Deepgram engine with card details removed
  from every transcript before Rasa records it
- `engines/rime_idle.py`: Rasa's Rime engine, reopening its socket after 20 s
  idle (from the Northgate advisor build)
- `hooks.py`: observers only: the model-request card scan and the hook-point
  counters
- `skills/default_session_start/`: binds the signed-in customer, then greets
- `skills/pay_order_balance/`: the skill, its tools (`look_up_order_balance`,
  `prepare_secure_payment`, `send_secure_payment_link`,
  `check_payment_status`, `leave_payment_pending`), the confirmation question
  and the prepared-payment memory
- `tools/willowshop_session.py`: `load_session_customer`
- `lib/pci.py`: finding and removing card details in text, no Rasa imports
- `lib/payments.py`: orders, the simulated processor, the case guard, the
  receipts and the fictional-organisation guard, no Rasa imports
- `lib/fixtures/`: fictional data and the vendored case contract
- `tests/`: offline guard, redaction and engine tests
- `case-build/`: scripted calls, the caller-audio manifest, three sample WAVs,
  the caller-audio script, the analysis script and recorded live results

## Ground rules

- No tool takes card details, and none may. Payment happens only through a
  processor-hosted link sent by text or email to the contact details on the
  account. `tests/test_guard.py` fails if a tool gains a card, expiry or
  security-code parameter.
- The guard lives in `lib/payments.py`. `recorder_excluded` needs the
  redacting speech-to-text engine running in the process and no card
  details in the caller's messages; do not relax either to make a call pass.
- Keep `engines/deepgram_pci.py` on both channels. Swapping it for the plain
  `deepgram` engine puts card numbers in the tracker, the model request and
  the log, and the payment tools then refuse to start.
- `lib/payments.py` refuses fixture data whose organisation is not exactly the
  casebook contract's organisation marked `(fictional)`. Keep no list of real
  institution names anywhere in this project: the repository's
  fictional-data lint rejects them in every tracked file.
- Read fixture files at import time. Mantle imports `lib/` from a temporary
  snapshot that is removed after loading.
- Keep `lib/fixtures/case-contract.json` identical to the casebook copy;
  `tests/test_guard.py` checks it.
- Keep every memory value under 100 characters: Mantle cuts longer values in
  the prompt without saying so. A test checks every order and channel.
- Match straight and curly apostrophes in every pattern.
- Leave `utter_on_user_denial` unset: with one, a correction at the
  confirmation question gets only the canned line.
- Caller WAVs are named from their voice and text and kept out of git except
  the three samples. Changing a caller line in `case-build/conversations.json`
  needs `make caller-audio` (billed Gemini TTS); `make check-caller-audio`
  compares local files with the manifest.
- After a change: `make proof`, `make validate`, `make train`. A change to
  skills, tools, engines or `lib/` makes the recorded results stale until the
  calls are rerun.
