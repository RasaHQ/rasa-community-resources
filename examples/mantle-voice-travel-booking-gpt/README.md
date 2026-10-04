# Horizon Travel journey changes with Rasa Pro Mantle

```text
Author:        Rasa Community
Assessed on:   2026-10-04
Assessed by:   Codex (tutorial source and publication-boundary review)
Verified with: Python 3.12; uv.lock pins rasa-pro 3.21.0.dev5
```

A browser voice tutorial for changing a selected flight together with its
linked services. Horizon Travel, its travellers, bookings and partner records
are fictional. The example uses Rasa Pro Mantle, GPT, Deepgram and Rime.

## Run the tutorial

```sh
make install
make env
make proof
make validate
make train
make inspect
make run
```

Set `RASA_LICENSE`, `OPENAI_API_KEY`, `DEEPGRAM_API_KEY` and `RIME_API_KEY`
locally using `.env.example`. Live provider calls are billed by those
providers. Never commit credentials, generated logs or result files.

Try: "Booking H Z four R eight N. Move my Lisbon to Boston flight tomorrow
to the later one that afternoon." Use the Inspector to inspect the selected
segment, proposed change, confirmation and linked-service receipts.

## Journey change boundary

The signed-in traveller comes from session memory. Tools select the booking
and segment, prepare the proposed change and write its confirmation fields.
The skill uses `requires_confirmation` before applying the journey change.

`lib/journeys.py` checks the selected segment and every linked service. It
reconciles receipts after a change and returns the result for the caller.
If a linked service needs assistance, the tool records the pending state and
provides a travel-desk reference. The code handles the journey as one unit.

The fictional records and contract are in `lib/fixtures/`. Offline tests
cover segment selection, linked services, receipts and repeated requests.
`case-build/conversations.json` supplies synthetic caller fixtures.

## Local reproduction

```sh
make caller-audio
make check-caller-audio
make conversations
make analyse RUN=<your-local-label>
```

These commands generate local audio and output. Keep generated material
outside public source commits. Retain the dependency lock and only create
this environment while working on the tutorial.
