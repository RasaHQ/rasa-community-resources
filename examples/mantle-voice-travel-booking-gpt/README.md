# Horizon Travel journey changes on GPT-5.5 with Deepgram and Rime: a voice agent that never changes one flight on its own

```text
Author:        Rasa Community
Assessed on:   2026-09-30
Assessed by:   Claude Code (casebook case builds; live runs recorded in case-build/results/)
Verified with: rasa-pro 3.21.0.dev5, Python 3.12, uv
Audience:      Engineers putting booking changes behind a Rasa voice agent
Time:          15 minutes to run the agent; the live call suite has not completed (see Results)
```

A Rasa Mantle voice agent for one casebook case,
[`travel-booking`](../../tutorials/rasa-ai-team-casebook/examples/travel-booking.json):
change a selected flight on a signed-in Horizon Travel traveller's booking,
together with everything linked to it. Horizon Travel is a fictional travel
company. The agent runs on `gpt-5.5-2026-04-23` at `reasoning_effort: low`,
hears the caller with Deepgram Flux and speaks with Rime Mist v3, over
Rasa's `browser_audio` WebSocket channel.

The case's failure is one sentence: *the agent changed one flight segment and
left a connecting service pointing at the old arrival time.* A prompt rule
cannot prevent that, because the model only sees what a tool returns. So this
project makes the journey the unit of change, in code:

1. **There is no flight-only change.** The one tool that changes a booking,
   `apply_journey_change`, finds every service linked to the segment (the
   connecting flight, transfers, the checked bag's routing, parking), checks
   each one, changes the segment, moves the services, and then compares every
   identifier with the new times.
2. **The caller confirms the journey, not the flight.** The engine's
   confirmation gate reads back the change and every linked service from
   memory only the tools write: "This moves your Lisbon to Boston flight on
   October 24 to H Z 2 1 9 at 3:30 PM the same day, and it affects your
   Denver connection, Lisbon hotel pickup, checked bag and Denver parking.
   Shall I check all of them before proceeding?"
3. **A partial change freezes the booking.** If a linked service still points
   at the old times after the change, the result is `pending`, the tool tells
   the caller which service was not changed, and the booking is handed to the
   travel desk with a reference. Further changes on it are refused, so the
   whole request is never repeated.

## Scope

- **Synthetic scenario.** Horizon Travel, its partners (Horizon Transfers,
  Horizon Park and Fly, Sierra Walks), the traveller Ines Calloway, her
  bookings, flights, references, a 555-01xx mobile number and an example.com
  address are invented (`lib/fixtures/`). Airport codes and city names are
  used only as places. `lib/journeys.py` refuses to load a fixture whose
  organisation is not exactly the casebook contract's, marked fictional.
- **The booking system is simulated** in process, one copy per call. The
  booking clock is the evening of October 23, 2026.
- **Synthetic callers.** Every caller line is AI-generated speech from Rime's
  `tundra` and `moraine` (Mist v2). Gemini TTS was asked first and refused
  at its daily cap (see The voice stack). No person's voice is recorded here.
- **What is measured so far:** one estimate call and a stopped main run (see
  Results). The 16-call suite in `case-build/conversations.json` is written,
  its caller audio is rendered, and it has not run to completion because the
  shared OpenAI key ran out of credit.

## Quick start

```bash
make install
make env        # then fill RASA_LICENSE, OPENAI_API_KEY, DEEPGRAM_API_KEY and RIME_API_KEY in .env
make proof      # offline guard, journey, receipt and engine tests: no licence, model or network
make validate
make train
make inspect    # talk to it in the Inspector, with a microphone
make run        # browser_audio WebSocket at ws://localhost:5005/webhooks/browser_audio/websocket
```

Try: "Booking H Z four R eight N. Move my Lisbon to Boston flight tomorrow
to the later one that afternoon." Then try the same flight on October 25:
the Denver parking cannot be extended, so the change is partial.

To run the scripted calls (billed GPT-5.5, Deepgram and Rime, capped at 4
USD across all runs by `case-build/results/spend-ledger.json`):

```bash
make caller-audio         # regenerate the caller WAVs that are not in git (Rime)
make check-caller-audio   # which local WAVs match the recorded SHA-256s
make conversations        # spoken caller audio, all 16 calls
make analyse RUN=<label>  # case metric, receipts, unheard turns, latency parts
```

## Required secrets

| Variable | Purpose |
|---|---|
| `RASA_LICENSE` | Rasa Pro Developer Edition licence |
| `OPENAI_API_KEY` | GPT-5.5, as `api_key: ${OPENAI_API_KEY}` in `integrations.yml` |
| `DEEPGRAM_API_KEY` | Deepgram Flux speech-to-text, read by Rasa's built-in `deepgram` engine |
| `RIME_API_KEY` | Rime text-to-speech for the agent; also renders the caller lines |

`GEMINI_API_KEY` is needed only if the caller lines are moved back to Gemini
voices. No Anthropic key is used: the live runs were made with
`ANTHROPIC_API_KEY` exported empty. The agent has no references, so there are
no embedding calls.

## How the guard works

The casebook lab gives the case two request rules and one receipt rule. The
tools enforce them in `lib/journeys.py`, in the contract's order. The model
supplies a booking (reference or trip city), its words for the flight, and
an option id from `find_change_options`. The traveller comes from the
signed-in session (project memory, written once at session start), and the
draft change is skill memory only `prepare_journey_change` writes.

| Rule (lab field) | Result when it fails | How the code decides | Fixture or call that breaks it |
|---|---|---|---|
| `segment_identity_confirmed` | `blocked` / `wrong_segment` | The draft is for this booking, its segment is open (not flown), and the segment still has the flight and departure it had when drafted. Words that fit more than one open segment return `needs_segment` instead of a draft | "My Boston flight tomorrow" on `HZ4R8N` fits two segments; a draft whose segment has moved since |
| `dependent_services_checked` | `blocked` / `connection_not_checked` | At commit, every linked service is found again from the booking, each one's status can be read, and the set is exactly the one read back to the caller | `HZ3M9V`: the Madrid tour partner's status cannot be read |
| `change_receipt_reconciled` | `pending` / `partial_journey_change` | After the change, each linked identifier is compared with the new segments: a connection leaves at least its minimum connection time after the new arrival, a transfer sits at its offset from the flight, the bag's routing lists the new flights, parking covers the new arrival | `HZ4R8N` moved to October 25: the Denver parking ends October 24 at 11:59 PM and its partner does not extend automatically |

A fact must be exactly `true`, as in the lab. `tests/test_journeys.py`
replays all ten of the lab's variants against this code, including the three
string-`"true"` variants.

`apply_journey_change` sits behind the engine's `requires_confirmation` gate,
which reads the case's question back from the draft memory. The gate sets no
`utter_on_user_denial`, so a correction at that question ("No, I meant the
return leg") is answered in the same turn (the Willow Shop returns build ran
both ways). Every memory value is kept under 100 characters, because Mantle
cuts longer values in the prompt without saying so; a test checks every
option of every booking.

Flight status is a separate tool and a separate fact. `check_flight_status`
says `HZ 215` is 40 minutes late on October 24 and that nothing on the
booking changed because of it; `look_up_trip` reads the booking.

The change tool sends the caller its own receipt through `ToolContext.send`:
the new flight, each linked service's state and the change reference, or on
a partial change the unresolved service and the travel-desk reference. The
Northgate claim-intake and collections builds found that a receipt left to
the model often never reaches the customer. On voice that send waits while
the receipt is spoken, and Mantle counts the wait against `tool_timeout`
(the collections build), so `agent.yml` sets `tool_timeout: 30`. The longest
receipt this fixture can produce is 356 characters (a partial change); a
test holds every receipt under 380.

## Results

No full run has completed. What was recorded:

| Run | Calls | What happened |
|---|---|---|
| `case-build/results/estimate/` | 1 (`recovery-partial-parking-freeze`) | Failed: the booking was never found (below). 4 caller turns |
| `case-build/results/2026-09-30-stopped-openai-no-credit/` | 2 started | OpenAI refused 14 of 15 model calls: "You have no credits remaining". Stopped under the programme's quota rule; nothing here is evidence about the agent |

**The estimate call.** The caller spelled the booking code "H Z four R
eight N". Deepgram Flux wrote "Booking h z four r eight and please move my
Lisbon to Boston flight…": the final letter N became the word "and".
GPT-5.5 then called `find_change_options` twice with `booking: "HZ4R8"`, and
the agent asked the caller to repeat the reference; the change never
started. This is one call. The tools now fall back to the caller's own words
in the tracker when the model's argument holds no known reference, reading
"and" as N (`JourneyService.find_booking`, with a test); that fix has not
run live.

From the same call (n = 4 turns, so indicative only): end of caller speech
to first bot audio p50 1.29 s, p95 3.81 s. Of that, Rasa processing p50
0.87 s, Rime first byte p50 0.17 s, and the remainder (end-of-turn detection
before Rasa had a transcript, and transport) p50 0.35 s. GPT-5.5's time to
first token was p50 0.76 s (Mantle's `latency_breakdown`, 3 turns). All 4
caller turns produced exactly one user event: 0 heard as nothing, 0 split,
and no `voice_channel.audio_missing`. The call made 13 model calls, 3.25 per
caller turn, and 30% of prompt tokens came from OpenAI's cache (7,168 of
24,201).

## What we found

1. **A spelled booking code lost its last letter between speech-to-text and
   the model.** Flux transcribed "N" as "and"; GPT-5.5 passed the five
   characters before it. The transcript still held all six, so the lookup
   now reads the caller's words when the model's argument does not match.
   One call; the rerun is pending.
2. **The harness's console line hides a provider error.** When OpenAI ran out
   of credit, the harness printed `FAIL` for the first call. Its own
   classification of that call, recomputed offline from the usage log, is
   `provider_error`; the console prints only PASS or FAIL. The run would
   have stopped after the second call by the harness's two-errors rule.

## The voice stack

- **Speech-to-text:** Deepgram `flux-general-en` through Rasa's built-in
  `deepgram` engine, `eot_threshold: 0.7`, `eot_timeout_ms: 5000`, as in the
  Northgate block-card build. No `language` key: Rasa sends it to Flux as
  `language_hint`, which only `flux-general-multi` accepts (the Northgate
  advisor build).
- **Text-to-speech:** Rime `mistv3`, speaker `peak` (Rime's catalogue: "a
  confident, professional young American voice"), through
  `engines.rime_idle.RimeTTSReconnectOnIdle` from the Northgate advisor build
  (Rime's socket goes quiet after about 30 s idle, and the built-in engine
  never reopens it).
- **Caller audio:** Gemini `gemini-3.8-flash-tts` rendered one line at
  19:15 UTC, then refused with HTTP 429 at its 100-requests-per-model daily
  cap, which other builds on the key had used that day. That file is not
  used; its cost is in the ledger. All 16 conversations were moved to Rime's
  `tundra` and `moraine` (Mist v2, US English in Rime's catalogue): 44 lines.
  Neither caller vendor is the build's speech-to-text vendor, so no vendor
  transcribes its own voice. Three WAVs are committed as samples: tundra
  spelling the booking code (`tundra-621cffbf3569.wav`), moraine's bare
  "Yes." (`moraine-63733c998be7.wav`), and tundra asking about another
  traveller's booking (`tundra-0138ae998abd.wav`). The rest are listed in
  `case-build/caller-audio/manifest.json` with their SHA-256s.

## Spend

All recorded in `case-build/results/spend-ledger.json`, 0.24 USD against a
4 USD cap:

| Vendor | USD | What |
|---|---|---|
| OpenAI (GPT-5.5) | 0.113 | model calls priced by LiteLLM 1.101.2's bundled map: 0.103 estimate, 0.010 stopped run; refused calls are not priced |
| Rime (caller) | 0.073 | 44 caller files at 0.03 USD per 1,000 characters |
| Rime (agent) | 0.036 | characters of bot text at 0.03 USD per 1,000 (an upper bound: Rasa's TTS cache can serve a repeat) |
| Deepgram | 0.015 | seconds streamed to Flux at 0.0065 USD a minute, silence included |
| Gemini TTS (caller) | 0.002 | one caller file, from the usage Gemini returned; not used |
| Anthropic | 0 | not used |

The second call of the stopped run was interrupted before the harness wrote
its record, so its speech entry is an upper bound from the server log (35 s
of call wall time; 299 characters of bot text) and is labelled as such.

## Project layout

| Path | What |
|---|---|
| `agent.yml` | Persona, rules, voice rules, `tool_timeout: 30` |
| `integrations.yml` | GPT-5.5 model group (`reasoning_effort: low`); `browser_audio` and `inspector` with Deepgram and Rime |
| `engines/rime_idle.py` | Rime with an idle reconnect |
| `skills/change_travel_booking/` | The skill, its six tools, the confirmation question, the draft-change memory |
| `skills/default_session_start/`, `tools/horizon_session.py` | Binds the signed-in traveller, then greets |
| `lib/journeys.py` | Bookings, journey plan, guard, reconciliation, receipts, fictional-organisation guard |
| `lib/fixtures/` | Fictional data and the vendored case contract |
| `tests/` | Offline guard, journey, memory-limit, receipt and engine tests |
| `case-build/` | Scripted calls, caller-audio manifest and samples, render and analysis scripts, recorded runs |
