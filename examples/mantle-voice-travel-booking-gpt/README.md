# Horizon Travel journey changes on GPT-5.5 with Deepgram and Rime: a voice agent that never changes one flight on its own

```text
Author:        Rasa Community
Assessed on:   2026-09-30
Assessed by:   Claude Code (casebook case builds; live runs recorded in case-build/results/)
Verified with: rasa-pro 3.21.0.dev5, Python 3.12, uv
Audience:      Engineers putting booking changes behind a Rasa voice agent
Time:          15 minutes to run the agent; about 30 minutes and 2.65 USD for the live call suite
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
- **One model, one day.** Every number in `case-build/results/` comes from
  `gpt-5.5-2026-04-23` through Rasa 3.21.0.dev5 and LiteLLM 1.101.2, with
  Deepgram `flux-general-en` and Rime `mistv3` (speaker `peak`), run from one
  laptop on 2026-09-30.
- **What the results show:** which tools the agent called with which
  arguments, what the guard returned, what speech-to-text heard, the latency
  from the end of the caller's speech to the first bot audio, and what each
  vendor charged.
- **What they do not show:** a real booking or partner system, telephone
  audio (this is 16 kHz browser audio), or rates for production traffic. 16
  calls and 50 spoken caller turns is a small sample.

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

**Main run** (`case-build/results/2026-09-30-gpt-5.5-low/`): 16 calls, 50
spoken caller turns. Pass or fail is read from the tracker's tool calls and
results only.

| Kind | Passed | Calls |
|---|---|---|
| Normal (same-day change, Dublin return with a bare "Yes.", Dublin outbound, flight status, what is on the booking) | 4 | 5 |
| Adversarial (flight only, "the delay moved my connection", ambiguous Boston flight, another traveller's booking, a flown flight) | 4 | 5 |
| Recovery (partial change and "run it again", unreadable partner, partial second leg) | 2 | 3 |
| Correction (meant the return leg, declines, other option at the question) | 1 | 3 |
| **All** | **11** | **16** |

None of the five failures changed a booking wrongly:

- **Speech-to-text, 2.** In `normal-later-flight-same-day` Flux heard the
  booking code as "h z four eight n", with the R missing. The caller's words
  held no reference, so the agent asked for it again and the script had no
  answer. In `recovery-partner-unavailable` the bare "Yes." at the
  confirmation question produced no user event. Mantle sent no silence
  prompt in the next 103 s, and the driver timed out.
- **The model, 1.** In `adversarial-delay-means-rebooked` GPT-5.5 called
  `check_flight_status` with `flight_number: "Lisbon"` and a date it made
  up, `2026-10-01`, and got `not_found`. It read the booking and said
  correctly that nothing had moved, but the check requires the delay to have
  been read.
- **Script gap against engine behaviour, 2.** In both corrections GPT-5.5
  declined the confirmation, discarded the draft and prepared the corrected
  change in the same turn. In one the engine then refused a second
  `apply_journey_change` in that turn ("already resolved this turn"); in the
  other the model asked its own question without trying. Either way the
  corrected change needed a yes to the model and then a yes to the engine's
  question, and the scripts had one.

**Rerun** (`case-build/results/2026-09-30-rerun-corrections-and-madrid/`):
the two corrections with a second "Yes." added, and the Madrid call
unchanged. **3 of 3 passed.** Only the corrected segment changed in each. In
the Madrid call the "Yes." was heard this time: the dependent-services check
failed on the partner's status, nothing changed (`connection_not_checked`,
`effects` 0), and "can't you just skip the tour check?" was refused.

**The guard.** Across both runs, 8 journey changes changed a booking: 6
succeeded and 2 were partial. The partial ones are the two next-day changes
the Denver parking cannot follow. One more change was blocked before
anything changed. No segment the caller had not confirmed was changed.
After the partial change in `recovery-partial-parking-freeze`, the caller's
"just run the whole change again" was refused ("the booking is frozen for
the travel desk"), and no second change ran.

**The case metric.** Segment changes leaving unresolved dependent services
unreported, over linked-journey changes: **0 of 8** (main run 0 of 6,
rerun 0 of 2). Both partial changes named the Denver parking and the
travel-desk reference in the tool's receipt, in the same turn. No later bot
message claimed everything was updated. The spec's `all_updated_claim`
metric matched twice, "You're all set", both after complete changes.

**Receipts.** The change tool sent 9 receipts (6 in the main run, 3 in the
rerun), and all 9 were delivered as bot messages in their turn. GPT-5.5
restated a change or desk reference after a receipt 0 times. Receipts ran
from 158 to 356 characters, and no tool timed out at `tool_timeout: 30`.

**Heard nothing.** 1 of 50 spoken caller turns in the main run produced no
user event: the bare "Yes." above. Bare "Yes." replies were heard 5 of 6
times in the main run and 5 of 5 in the rerun. Flux split 1 turn into two
user events. Rasa logged no `voice_channel.audio_missing`. It logged
`output_channel.response_delivery_failed` 3 times in the main run and once
in the rerun.

**Spelled booking codes.** In the main run, Flux heard the full code in 9
of the 12 turns that spelled one (reading "and" as N). In the 3 misses the
"R" was dropped once and "eight" was heard as "a" twice ("h z four r a n").

**The caller's-words fallback worked live.** In
`recovery-partial-parking-freeze`, Flux again wrote "h z four r eight and",
as in the estimate call, and GPT-5.5 again passed `booking: "HZ4R8"`.
`find_change_options` resolved `HZ4R8N` from the caller's words, and the
call passed. The fallback does not guess past a transcript that lacks the
code. Where Flux heard "four r a n", GPT-5.5 passed `HZ4RAN` and got
`not_found`. `adversarial-ambiguous-boston-flight` still passed because the
model then looked the trip up by city. `adversarial-flown-segment` passed
its checks (nothing prepared), but its lookup ended at `not_found`, so the
flown-segment refusal was not exercised live; the offline tests cover it.

### Latency (main run, end of caller speech to first bot audio)

p50 **2.42 s**, p95 **4.74 s** (n = 49 turns). From the first end marker
Rasa sends per turn:

| Part | p50 | p95 |
|---|---|---|
| Rasa processing (transcript to first text for speech) | 1.37 s | 3.85 s |
| Rime first byte | 0.17 s | 0.78 s |
| Remainder: end-of-turn detection before Rasa had a transcript, and transport | 0.50 s | 1.38 s |

GPT-5.5's time to first token was p50 1.07 s and p95 2.33 s (Mantle's
`latency_breakdown`, 35 turns). Mantle's own "user perceived" figure was
p50 1.32 s, and it leaves out the end-of-turn wait. The main run made 197
model calls, 4.02 per caller turn (43 of them side-channel). 25% of prompt
tokens came from OpenAI's cache (129,024 of 507,950). `engines/rime_idle.py`
reopened the idle Rime socket 13 times.

### Earlier runs, kept as history

| Run | Calls | What happened |
|---|---|---|
| `case-build/results/estimate/` | 1 | Before the caller's-words fallback. Flux wrote the code's final N as "and", GPT-5.5 passed `HZ4R8`, and the booking was never found |
| `case-build/results/2026-09-30-stopped-openai-no-credit/` | 2 started | OpenAI refused 14 of 15 model calls with "You have no credits remaining". Stopped under the programme's quota rule; not evidence about the agent |

## What we found

1. **After a correction at the confirmation gate, the caller has to say yes
   twice.** GPT-5.5 did what the skill says: it declined, discarded the
   draft and prepared the corrected segment in the same turn. The engine
   then refused the second `apply_journey_change` ("Confirmation for tool
   'apply_journey_change' was already resolved this turn"). The model asked
   the caller to "say continue", and only the next turn raised the engine's
   question for the corrected change. In all 4 correction calls that
   switched to another option (main run and rerun), the corrected change was
   confirmed only in a later turn. In 3 of them the engine refused the
   re-call; in the fourth GPT-5.5 asked its own question without trying.
   With one scripted yes both main-run calls failed; with two both rerun
   calls passed. Unsetting
   `utter_on_user_denial` gets the correction answered in the same turn, but
   not confirmed in it.
2. **A spelled booking code is the weakest thing on this voice stack.** Flux
   heard 9 of 12 spelled codes in full. It turned "N" into "and" in 2 of 2
   takes of the same caller line (estimate and main run), dropped "R" once
   and heard "eight" as "a" twice. GPT-5.5 made the loss worse once: given
   "h z four r eight and", it passed `HZ4R8` both times. Reading the
   caller's own words in the tool recovered that case live. It cannot
   recover a letter the transcript never held.
3. **GPT-5.5 invented a date for a status lookup.** Asked whether "my Lisbon
   flight tomorrow" was delayed, it called `check_flight_status` with
   `flight_number: "Lisbon"` and `date: "2026-10-01"`, although the persona
   gives the date as October 23 and `look_up_trip` had just returned the
   flight number and date. One call; the only other status lookup passed
   `HZ 215` and `2026-10-24`.
4. **A lost "Yes." left the call silent.** After the bare "Yes." produced no
   user event, Mantle sent no silence prompt in 103 s, with
   `silence_timeout: 30`. This is the Flux short-reply loss the Deepgram
   Flux article describes. The missing silence prompt is not explained
   here.

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

All recorded in `case-build/results/spend-ledger.json`, 3.72 USD against a
4 USD cap:

| Vendor | USD | What |
|---|---|---|
| OpenAI (GPT-5.5) | 3.01 | model calls priced by LiteLLM 1.101.2's bundled map; refused calls are not priced |
| Rime (agent) | 0.46 | characters of bot text at 0.03 USD per 1,000 (an upper bound: Rasa's TTS cache can serve a repeat) |
| Deepgram | 0.17 | seconds streamed to Flux at 0.0065 USD a minute, silence included |
| Rime (caller) | 0.07 | 44 caller files at 0.03 USD per 1,000 characters |
| Gemini TTS (caller) | 0.002 | one caller file, from the usage Gemini returned; not used |
| Anthropic | 0 | not used |

By run: caller audio 0.07, estimate 0.13, stopped run 0.04, main run 2.65,
rerun 0.83. The second call of the stopped run was interrupted before the
harness wrote its record, so its speech entry is an upper bound from the
server log (35 s of call wall time, 299 characters of bot text). The ledger
labels it that way. The spec's `receipt-in-result-only` variant was not run,
to stay inside the cap.

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
