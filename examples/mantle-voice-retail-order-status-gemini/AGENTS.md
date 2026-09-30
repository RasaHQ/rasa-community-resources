# Rasa Skills project: Willow Shop order status (Gemini, browser voice)

This directory is a **Rasa Mantle** voice agent built for one casebook case,
`retail-order-status`. Willow Shop is a fictional retailer and Larkspur
Parcel a fictional carrier.

Pin: `rasa-pro==3.21.0.dev5`. LLM: `gemini-3.8-flash` through the `gemini`
provider (LiteLLM). Speech: Deepgram Flux (`flux-general-en`) in, Rime Mist v3
(speaker `lagoon`) out. Channels: `browser_audio` (raw WebSocket) and
`inspector`.

## Layout

- `agent.yml`: identity, persona, rules and voice rules (siblings of `agent:`)
- `integrations.yml`: the Gemini model group and both voice channels. Mantle
  reads channels here; it never reads `credentials.yml`
- `memory.yml`: project memory, written by `load_session_customer` only
- `responses.yml`: the greeting
- `skills/default_session_start/`: binds the signed-in customer, then greets
- `skills/order_status/`: the skill and its tools (`list_orders`,
  `track_order`, `open_delivery_help`)
- `tools/willowshop_session.py`: `load_session_customer`
- `lib/orders.py`: order tracking, the case guard and the fictional-organisation
  guard, no Rasa imports
- `lib/fixtures/`: fictional data and the vendored case contract
- `tests/`: offline guard tests
- `case-build/`: scripted calls, the caller-audio manifest, three sample WAVs,
  the caller-audio regeneration script and recorded live results

## Ground rules

- The guard lives in `lib/orders.py`. The model supplies an order number and
  a parcel number; the customer id comes from project memory, and the three
  contract facts are computed from fixture data.
- A label is a warehouse event. Only a carrier scan can say the carrier has a
  parcel or delivered it; `milestone_explicit` enforces the source per
  milestone. Never add a tool that reports a status from an unlabelled record.
- `lib/orders.py` refuses fixture data whose retailer or carrier is not
  marked fictional or names a real one. Keep the fixture fictional.
- Read fixture files at import time. Mantle imports `lib/` from a temporary
  snapshot that is removed after loading.
- Keep `lib/fixtures/case-contract.json` identical to the casebook copy;
  `tests/test_guard.py` checks it.
- Caller WAVs are named from their voice and text and kept out of git except
  the three samples. Changing a caller line in `case-build/conversations.json`
  needs `make caller-audio` (billed Gemini TTS); `make check-caller-audio`
  compares local files with the manifest.
- Do not use OpenAI anywhere in this build (no model, embeddings or caller
  audio): the build was made without OpenAI credit, and its receipts say so.
- After a change: `make proof`, `make validate`, `make train`. A change to
  skills, tools or `lib/` makes the recorded results stale until the calls
  are rerun.
