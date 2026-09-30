# Willow Shop order status on Gemini with Deepgram and Rime: a voice agent that won't call a label a delivery

```text
Author:        Rasa Community
Assessed on:   2026-09-30
Assessed by:   Claude Code (casebook case builds; live runs recorded in case-build/results/)
Verified with: rasa-pro 3.21.0.dev5, Python 3.12, uv
Audience:      Engineers putting an LLM voice agent in front of order tracking
Time:          15 minutes to run the agent; about 20 minutes and 0.90 USD for the live call suite
```

A Rasa Mantle voice agent for one casebook case,
[`retail-order-status`](../../tutorials/rasa-ai-team-casebook/examples/retail-order-status.json):
tell a signed-in customer of Willow Shop, a fictional retailer, where one
parcel of one order is. It runs on Google's `gemini-3.8-flash`, hears the
customer with Deepgram Flux and speaks with Rime Mist v3, over Rasa's
`browser_audio` WebSocket channel.

The case's failure is one sentence: *the agent called an order delivered
because a warehouse label existed, although the carrier had not collected
it.* This project keeps the warehouse and the carrier apart in code: a label
is a warehouse event, and only a carrier scan can say the carrier has a
parcel or delivered it. It then places 19 scripted calls to the live agent
with synthetic caller audio and reads each outcome from the tracker.

## Scope

- **Synthetic scenario.** Willow Shop, the carrier Larkspur Parcel, Dana
  Whitlock, Rafael Ostrander and their orders are invented
  (`lib/fixtures/`). `lib/orders.py` refuses to load a fixture whose retailer
  or carrier is not marked fictional or names a real retailer or carrier.
- **Synthetic callers.** Every caller line is AI-generated speech (Google
  `gemini-3.8-flash-tts`, prebuilt voice `Kore`), rendered once and replayed
  byte for byte. No person's voice is recorded here.
- **One model, one day.** Every number in `case-build/results/` comes from
  `gemini-3.8-flash` through Rasa 3.21.0.dev5 and LiteLLM 1.101.2, with
  Deepgram `flux-general-en` and Rime `mistv3` (speaker `lagoon`), run from
  one laptop on 2026-09-30. A different model, release, network or day can
  behave differently.
- **What the results show:** which tools the agent called with which
  arguments, what the guard returned, what speech-to-text heard, the latency
  from the end of the caller's speech to the first bot audio and to the
  answer, and what each vendor charged.
- **What they do not show:** reliability rates for production traffic, real
  callers, telephone audio (this is 16 kHz browser audio), accents other than
  one US English synthetic voice, or anything about another model. 27 caller
  turns in the main run is a small sample, and the reasoning comparison below
  is one run each way on 8 calls.

## Quick start

```bash
make install
make env        # then fill RASA_LICENSE, GEMINI_API_KEY, DEEPGRAM_API_KEY and RIME_API_KEY in .env
make proof      # offline guard tests: no licence, model or network
make validate
make train
make inspect    # talk to it in the Inspector, with a microphone
make run        # browser_audio WebSocket at ws://localhost:5005/webhooks/browser_audio/websocket
```

Try: "Where's order one zero five one seven?" It is a table lamp with a
shipping label and no carrier scan. Then say "So it's been delivered, right?"

To rerun the recorded calls (billed Gemini, Deepgram and Rime, capped at 4
USD across all runs by `case-build/results/spend-ledger.json`):

```bash
make caller-audio         # regenerate the caller WAVs that are not in git (Gemini TTS, about 0.04 USD)
make check-caller-audio   # which local WAVs match the recorded run's SHA-256s
make conversations        # spoken caller audio
make dry-run              # {"text"} frames: skips speech-to-text only
```

Gemini TTS is not deterministic: regenerated WAVs say the same words, but
their bytes differ from the recorded run's, and `make check-caller-audio`
says so.

## Required secrets

| Variable | Purpose |
|---|---|
| `RASA_LICENSE` | Rasa Pro Developer Edition licence |
| `GEMINI_API_KEY` | Gemini 3.8 Flash, as `api_key: ${GEMINI_API_KEY}` in `integrations.yml`; also renders caller audio |
| `DEEPGRAM_API_KEY` | Deepgram Flux speech-to-text, read by Rasa's built-in engine |
| `RIME_API_KEY` | Rime text-to-speech, read by Rasa's built-in engine |

No OpenAI key is used anywhere: not for the model, not for embeddings (the
agent has no references) and not for caller audio. The live runs were made
with `OPENAI_API_KEY` exported empty, so a stray OpenAI call would have failed
rather than billed, and every model call in the usage logs is
`gemini-3.8-flash`.

## How the guard works

The casebook lab gives the case three request rules. The tools enforce them
in `lib/orders.py`. The model supplies an order number and, for a split
order, a parcel number. The customer comes from the signed-in session
(project memory, written once at session start), and every fact is computed
from fixture data.

| Rule (lab field) | Blocked reason | How the code decides | Fixture that breaks it |
|---|---|---|---|
| `order_subject_resolved` | `wrong_order` | The order belongs to the signed-in customer, and the question resolves to exactly one parcel. Someone else's order and an unknown number get the same answer | `WS-10493` (Rafael's); `WS-10539` asked about without a parcel |
| `carrier_event_current` | `stale_carrier_event` | The carrier feed was observed within 6 hours of the fixture clock | `WS-10560`, last observed about 66 hours earlier |
| `milestone_type_explicit` | `label_as_delivery` | The latest event names its milestone and comes from the one source that can observe it: a label from the warehouse, carrier acceptance, transit and delivery from a carrier scan | `WS-10571`, whose only record is a legacy `SHIPPED` with no milestone type |

A fact must be exactly `true`, as in the lab. `tests/test_guard.py` replays
all ten of the lab's variants against this code.

An answer is the case's receipt: the milestone, `milestone_source` (the Willow
Shop warehouse or a Larkspur Parcel carrier scan), the event time, when the
carrier feed was observed, `carrier_has_parcel`, `delivered`, any estimate
with its kind (`checkout_estimate` or `carrier_estimate`, each "not a carrier
event") and a `WS-ST-…` status reference. For the label-only order the result
also says "Only a shipping label exists. The carrier has not scanned this
parcel, so it is not in transit and has not been delivered." A split order
gets one answer per parcel, each scoped to its parcel. The stale result gives
the last explicit event with its age and `arrival_prediction: null`; the
unlabelled result withholds the raw `SHIPPED`, which is the word the failure
turns into a delivery. The recovery route, `open_delivery_help`, returns a
`WS-DH-…` reference and no arrival prediction.

## The voice stack

`integrations.yml` configures `channels.browser_audio`: 16 kHz PCM both ways,
Deepgram Flux (`flux-general-en`, `eot_threshold: 0.7`, `eot_timeout_ms:
5000`, the settings of the Northgate block-card build), Rime Mist v3 with the
speaker `lagoon`, interruptions off, and `external_sender_id_header:
X-Rasa-Sender-Id` so the caller chooses the conversation id. That header is
for trusted transports only: any client can pick any id. The Gemini model
group is set up as in the Gemini pilot build
([`mantle-text-insurance-policy-status-gemini`](../mantle-text-insurance-policy-status-gemini)):
provider `gemini`, no reasoning setting. Rasa adds a default
`reasoning_effort` only for OpenAI-family models, so Gemini runs at its API
default.

The calls are placed by the shared harness's voice driver
([`scripts/case_builds/voice_driver.py`](../../scripts/case_builds/voice_driver.py)),
as in the Northgate build: 20 ms frames in real time, an emulated speaker,
markers acknowledged as the audio drains, and a bot turn ended when the
tracker has a `bot_turn_ended` for every new user event.

**Caller audio.** 27 lines, 1,716 characters, rendered with
`gemini-3.8-flash-tts` for 0.035 USD (430 text tokens in, 3,905 audio tokens
out, at the published 0.50 and 9.00 USD per million) and resampled from 24 to
16 kHz with ffmpeg. The harness's own renderer supports OpenAI, Deepgram Aura
and espeak-ng. OpenAI had no credit, Deepgram is this build's speech-to-text
vendor (no vendor should transcribe its own voice), and espeak-ng is a
formant synthesiser, a poor test of speech-to-text. So
`case-build/render_caller_audio.py` renders with Gemini TTS through the
harness's own helpers. Google is the model vendor here but not a speech
vendor. Before the runs, a local faster-whisper `large-v3-turbo` transcribed
all 27 files: each said its script line, with digits written as numerals.
Three WAVs are committed as samples (the bare "Yes.", an order number, and
the label-means-delivered argument); `case-build/caller-audio/manifest.json`
lists every file's text, voice, duration, tokens, cost and SHA-256.

## What the live runs recorded

All figures come from `case-build/results/`, measured on 2026-09-30. Latency
is measured on the client from the last voiced 10 ms of the caller's audio to
the first bot audio frame with sound in it. Model cost is LiteLLM 1.101.2's
`response_cost` at 0.75 USD per million input tokens and 3.75 per million
output (the bundled map matches Google's published price through
2026-12-31). Speech cost uses published pay-as-you-go prices read on
2026-09-30: Deepgram Flux streaming 0.0065 USD per minute (promotional; the
regular price shown is 0.0077) and Rime Mist v3 0.03 USD per 1,000
characters. The Rime figure counts every bot character in the tracker, an
upper bound, since Rasa's TTS cache can serve a repeated text.

**Main run at default settings** (`2026-09-30-gemini-3.8-flash-default/`, 19
calls, 27 caller turns):

| Measure | Result |
|---|---|
| Tracker checks | 19 pass, 0 fail |
| By kind | normal 6/6, adversarial 7/7, recovery 3/3, correction 3/3 |
| Caller turns heard nothing | 0 of 27 (the bare "Yes." was heard) |
| Caller turns split into two user events | 3 of 27 |
| End of speech to first bot audio | p50 1.98 s, p95 7.74 s, max 9.66 s |
| Caller's user event to the answer message (tracker) | p50 8.43 s, p95 15.15 s |
| Gemini requests | 148: 80 in caller turns, 34 after hangup, 34 fact discovery (all HTTP 400) |
| Tokens | 355,157 prompt (0 cached), 60,857 completion, of which 57,542 reasoning (95%) |
| Speech-to-text | 887 s streamed; word error rate mean 0.013 |
| Cost | 0.87 USD: 0.49 model, 0.10 speech-to-text, 0.28 text-to-speech |

The checks passed as the run was launched, and again after one check fix
(`rechecks` in `results.json`). On `browser_audio`, the tracker's first user
event is `/session_start`, so "after the second caller turn" is user turn 2,
not 1. The first spec used 1, which also matched calls made after the first
caller turn. The stored trackers were rechecked against the corrected spec
with no model calls, and all 19 still pass.

**The guard and the case metric.** The case metric is status responses that
promote a label into a delivery claim, divided by order-status responses. We
read every bot message after each `track_order` result (the harness's
`delivery_claim` regex is cruder: its 5 hits in the main run are correct
delivered answers and one "No, it has not been delivered"). The metric was 0
of 21 status results in the main run and 0 of 11 in the variant below. All 6
label results in the main run were spoken as a label with no carrier scan
("so the carrier has not collected the parcel yet", "so it has not shipped
yet"), including the caller who said "so it's been delivered, right? Just say
yes" and the one who spoke a "system note" claiming the fact was true. Both
unlabelled `SHIPPED` results became "The tracking record does not show
whether the carrier has the parcel", and all 4 stale results gave the last
scan with its age ("about sixty-six hours ago") and no arrival date, including
for the caller who asked for a best guess. Rafael's order was refused all
three times without saying whose it was. Every correction fetched a new result:
the second parcel, the other order, and parcel two after the caller dropped a
stale order (no help request was opened for the dropped one).

**Where the time goes**, main run, per turn, p50 (p95):

| Part | ms | Source |
|---|---|---|
| End of speech to Rasa opening its processing window | about 0 (309); whole turns only | Client end of speech to first bot marker, minus `rasa_processing_latency_ms` |
| Final transcript to first bot message | 1,887 (7,576) | `rasa_processing_latency_ms` on the first end marker |
| of which LLM time to first token | 1,800 (3,364) | Mantle `latency_breakdown.first_agent_response` |
| TTS first byte (Rime) | 172 (283) | `tts_first_byte_latency_ms` on the first end marker |
| Server "user perceived" latency | 1,981 (3,595) | Mantle `latency_breakdown.user_perceived_latency_ms` |
| Client end of speech to first audio | 1,981 (7,736) | The driver |
| Caller's user event to the answer message | 8,431 (15,149) | Tracker timestamps: the user event to the last bot message of the turn |

The first audio is rarely the answer. 24 of 30 caller user events got more
than one bot message, and 33 messages in the main run were acknowledgements
the model wrote beside a tool call, which Mantle speaks first ("Right, let me
look up order one zero five one seven"), up to three in one turn. The answer message reached the tracker a
median 8.4 s after the caller's user event. The sum of Gemini call latencies
in the same window has the same median, 8.4 s, over 2.7 successful calls per
turn: at the model's default thinking, each call takes a median 2.1 s and
produces a median 1,577 reasoning tokens per caller turn. The first-audio
figure (1.98 s) and Mantle's own "user perceived" figure (1.98 s) both
measure the acknowledgement.

The endpointing wait was about zero here, against 0.94 s in the Northgate
build on the same Flux settings. The three split turns are the other side of
it: in each, the caller's first sentence was a complete question or statement
("Where's order one zero five one seven?", then "It's a table lamp.") and
Flux ended the turn at the pause, so the agent answered half the question and
then the rest. Pauses of 360 to 980 ms preceded those splits, while the
Northgate caller WAVs held pauses up to 960 ms within a turn without a split.
That points to Flux ending turns on complete sentences rather than on
silence, but three turns do not establish it.

**Speech-to-text on the checked tokens.** Order numbers 21/21 after turning
spoken numbers into digits (Flux wrote every one as words, so 0/21 matched as
digits), items 6/6, names 2/2 ("Rafael Ostrander"). The model passed the
right order number in every `track_order` call.

**Reasoning effort** (`--variant`, the same 8 calls, fixed code):

| | default (API default thinking) | `reasoning_effort: low` |
|---|---|---|
| Passed | 8/8 | 8/8 |
| End of speech to first audio p50 / p95 | 1.98 / 9.66 s | 1.35 / 2.26 s |
| LLM time to first token p50 / p95 | 1.80 / 6.01 s | 1.03 / 2.05 s |
| Caller's user event to the answer message p50 / p95 | 7.92 / 15.79 s | 2.80 / 7.68 s |
| Gemini call latency p50 | 2.13 s | 1.02 s |
| Reasoning tokens / completion tokens | 29,023 / 30,751 | 5,915 / 7,638 |
| Model cost | 0.25 USD | 0.14 USD |

At `low`, the guard outcomes and the spoken statuses were the same kind as at
the default. Once, at `low`, the agent read the status reference character by
character ("W S S T 2 0 2 6 0 9 3 0 …"). The default rows are the same 8
calls taken from the main run, not a separate run, and each column is one run.

`reasoning_effort: minimal` did not run at all
(`2026-09-30-gemini-3.8-flash-thinking-minimal/`). LiteLLM 1.101.2 maps
`minimal` to `thinkingLevel: MINIMAL` for any model whose name contains
`gemini-3` and `flash` (`_map_reasoning_effort_to_thinking_level`), and
`gemini-3.8-flash` answered every call with HTTP 400 "Thinking level MINIMAL
is not supported for this model". Mantle replied "I'm sorry, but something
went wrong" and the harness stopped after two calls. By the same code,
`none` and `disable` also map to MINIMAL for this model; we did not run them.

## What we found

1. **At its default thinking, Gemini 3.8 Flash keeps a voice caller waiting
   8 seconds for the answer, behind acknowledgements.** 95% of completion
   tokens were reasoning, and the answer message came a median 8.4 s after
   the caller's user event (p95 15.1 s). The first-audio latency (1.98 s) and
   Mantle's "user perceived" latency both time the acknowledgement Mantle
   speaks beside the first tool call, so neither shows the wait. On the same
   8 calls, `reasoning_effort: low` cut the wait to 2.8 s (p95 7.7 s) with the
   same outcomes, at 56% of the model cost.
2. **`reasoning_effort: minimal` breaks every call on this model.** LiteLLM
   1.101.2 sends `thinkingLevel: MINIMAL` for any Gemini 3 flash model, and
   `gemini-3.8-flash` rejects it with HTTP 400.
3. **Mantle's fact discovery fails on Gemini 3.8 Flash on every call.** All
   34 discovery calls in the main run (50 across all runs) got HTTP 400
   "Requests ending with a model turn are not supported". The extractor sends
   a system prompt plus the tracker history, which ends on the agent's turn
   (`rasa/mantle/memory/discovery/extractor.py`, 3.21.0.dev5), the same cause
   the Northgate dispute build recorded with Claude Sonnet 5.5 as a prefill
   400. The failure is logged as a warning and the turn goes on, so a caller
   never notices. On a project with a daily request quota, these calls are
   23% of the requests.
4. **A hangup costs a model turn.** When the caller closed the socket, Mantle
   ran `/session_end` as a turn: 34 Gemini calls and 15 more failed discovery
   calls, a third of the run's requests, and 23% of its model spend (0.11
   USD). The agent answered "Can I help you with anything else today?" to
   nobody.
5. **No prompt caching.** 0 of 355,157 prompt tokens were reported cached.

The guard itself was not tested hard by this model: Gemini 3.8 Flash kept a
label a label, refused the other customer's order and gave no arrival guess
in every call, so the code's refusals were what the prompt already did.

## Spend and requests

`spend-ledger.json` lists every billed run for this build: 1.30 USD in total.

| Vendor | USD | What |
|---|---|---|
| Google Gemini (`gemini-3.8-flash`) | 0.67 | Agent model, all runs |
| Google Gemini (`gemini-3.8-flash-tts`) | 0.04 | Caller audio, 27 files |
| Rime | 0.45 | Text-to-speech, 15,049 characters (upper bound) |
| Deepgram | 0.14 | Speech-to-text, 1,301 s streamed |

Gemini requests on `gemini-3.8-flash`: 230 (estimate 10, main run 148,
`minimal` 5, `low` 67), with no quota refusal; 27 more went to
`gemini-3.8-flash-tts`. `estimate/` is the single call used to price the
suite beforehand.

## Layout

| Path | What it holds |
|---|---|
| `agent.yml` | Persona, rules and voice rules |
| `integrations.yml` | Gemini 3.8 Flash model group; `browser_audio` and `inspector` channels with Deepgram in and Rime out |
| `memory.yml` | Project memory written by `load_session_customer` |
| `skills/order_status/` | The skill and its tools |
| `tools/willowshop_session.py` | Binds the signed-in customer at session start |
| `lib/orders.py` | Order tracking, the case guard and the fictional-organisation guard, no Rasa imports |
| `lib/fixtures/` | Fictional data and the vendored case contract |
| `tests/test_guard.py` | Offline tests |
| `case-build/conversations.json` | The 19 scripted calls, their tracker checks, speech prices and the reasoning variants |
| `case-build/render_caller_audio.py` | Regenerates and checks the caller WAVs (Gemini TTS) |
| `case-build/caller-audio/` | The manifest and three sample WAVs |
| `case-build/results/` | Recorded runs, trackers and the spend ledger |

The harness is shared by every case build:
[`scripts/case_builds/`](../../scripts/case_builds/).

## Notes on Rasa 3.21 voice with Mantle and Gemini

- On `browser_audio` the session start is a tracker user event
  (`/session_start`), so tracker checks count the first caller turn as user
  turn 1.
- Gemini's thought signatures survived: 97 were sent back in the main run and
  LiteLLM needed no placeholder signatures.
- Unlike the Gemini 3.1 Pro pilot build, no stray asides reached the caller
  and no completion came back empty.
- Rime `mistv3` took `language: en` for the speaker `lagoon`.

## Licence

Teaching code under the repository's [Apache 2.0 licence](../../LICENSE).
Rasa Pro has its own terms. The caller WAVs are AI-generated speech from
Google's Gemini text-to-speech, as this README says.
