# Northgate advisor appointments on Claude Sonnet 5.5 with Deepgram and Rime: a voice agent that won't book a mortgage question into a branch with no mortgage advisor

```text
Author:        Rasa Community
Assessed on:   2026-09-30
Assessed by:   Claude Code (casebook case builds; live runs recorded in case-build/results/)
Verified with: rasa-pro 3.21.0.dev5, Python 3.12, uv
Audience:      Engineers putting Claude behind a Rasa voice agent that books appointments
Time:          15 minutes to run the agent; about 35 minutes and 2.60 USD for the live call suite
```

A Rasa Mantle voice agent for one casebook case,
[`banking-advisor-appointment`](../../tutorials/rasa-ai-team-casebook/examples/banking-advisor-appointment.json):
book an advisor appointment for a signed-in customer of Northgate Bank, a
fictional UK bank, with a team that can handle what they asked about, on the
channel they want. It runs on `claude-sonnet-5-5`, hears the caller with
Deepgram Flux and speaks with Rime Coda, over Rasa's `browser_audio`
WebSocket channel. The scripted caller speaks British English.

The case's failure is one sentence: *the system booked a branch visit for a
question requiring a specialist who was not available at that branch.* This
project checks the purpose against the team's capability, holds a slot
before booking it, and checks the meeting channel and step-free access, all
in code, before the engine's confirmation gate reads the booking back. It
then places 15 scripted calls to the live agent with synthetic British
caller audio and reads each outcome from the tracker.

## Scope

- **Synthetic scenario.** Northgate Bank, its Kingsmere, Farrowdale and
  Ashcombe branches, its teams, Eleanor Hartwell and every slot are invented
  (`lib/fixtures/`). `lib/appointments.py` refuses to load a fixture whose
  organisation is not exactly the casebook contract's, marked fictional.
- **Synthetic callers, accent from the vendor's label, not verified by a
  listener.** Every caller line is AI-generated speech from Rime, in two
  voices Rime's public catalogue lists as British: `carol` (Mist v2, country
  UK, dialect British) and `albion` (Coda, country GB, dialect English).
  Nobody on the build team has listened to the files. Three are kept as
  samples (see The voice stack). No person's voice is recorded here.
- **One model, one day.** Every number in `case-build/results/` comes from
  `claude-sonnet-5-5` through Rasa 3.21.0.dev5 and LiteLLM 1.101.2, with
  Deepgram `flux-general-en` and Rime `coda` (speaker `vashti`), run from one
  laptop on 2026-09-30. A different model, release, network or day can
  behave differently.
- **What the results show:** which tools the agent called with which
  arguments, what the guard returned, what speech-to-text heard, the latency
  from the end of the caller's speech to the first bot audio, and what each
  vendor charged.
- **What they do not show:** rates for production traffic, real British
  callers, regional accents, telephone audio (this is 16 kHz browser audio),
  or anything about another model. 15 calls and 47 spoken caller turns is a
  small sample. Three calls planned for the suite were cut after the estimate
  to fit the 4 USD cap (see Spend).

## Quick start

```bash
make install
make env        # then fill RASA_LICENSE, ANTHROPIC_API_KEY, DEEPGRAM_API_KEY and RIME_API_KEY in .env
make proof      # offline guard and engine tests: no licence, model or network
make validate
make train
make inspect    # talk to it in the Inspector, with a microphone
make run        # browser_audio WebSocket at ws://localhost:5005/webhooks/browser_audio/websocket
```

Try: "Just book me in at Kingsmere with whoever's free. I'll ask them about
my mortgage when I'm there." Kingsmere has no mortgage advisor.

To rerun the recorded calls (billed Claude, Deepgram and Rime, capped at 4
USD across all runs by `case-build/results/spend-ledger.json`):

```bash
make caller-audio         # regenerate the caller WAVs that are not in git (Rime, about 0.09 USD)
make check-caller-audio   # which local WAVs match the recorded run's SHA-256s
make conversations        # spoken caller audio
make dry-run              # {"text"} frames: skips speech-to-text only
```

## Required secrets

| Variable | Purpose |
|---|---|
| `RASA_LICENSE` | Rasa Pro Developer Edition licence |
| `ANTHROPIC_API_KEY` | Claude Sonnet 5.5, as `api_key: ${ANTHROPIC_API_KEY}` in `integrations.yml` |
| `DEEPGRAM_API_KEY` | Deepgram Flux speech-to-text, read by Rasa's built-in engine |
| `RIME_API_KEY` | Rime text-to-speech for the agent; also renders the caller audio |

No OpenAI key is used anywhere: not for the model, not for embeddings (the
agent has no references) and not for caller audio. The live runs were made
with `OPENAI_API_KEY` exported empty, so a stray OpenAI call would have failed
rather than billed.

## How the guard works

The casebook lab gives the case three request rules. The tools enforce them
in `lib/appointments.py`, in the contract's order. The model supplies a
purpose word, a slot id copied from a search result and search filters. The
customer comes from the signed-in session (project memory, written once at
session start); the held slot is skill memory only the tools write; and the
customer's purpose, meeting channel and step-free need are read from their
own messages in the tracker, which on a voice call is what Deepgram heard.

| Rule (lab field) | Blocked reason | How the code decides | Fixture that breaks it |
|---|---|---|---|
| `purpose_matched` | `wrong_advisor_capability` | The purpose named in the customer's latest message that names one (mortgage, investments, business banking, everyday banking) is one the slot's team can handle, and the model's purpose word agrees with it. A specialist question never reaches a general team, even if the model or the customer relabels it | Kingsmere has everyday banking only; a mortgage or pension question there has no capable team |
| `slot_held` | `slot_not_held` | The scheduling service holds that slot for this call, the hold has not lapsed, and it is the slot the engine read back | `SLT-KGM-0714` is taken between proposal and hold; the first hold on `SLT-INV-V0913` lapses before booking |
| `channel_confirmed` | `wrong_meeting_channel` | The slot's channel (branch, phone or video) is the one the customer last asked for, a branch is step-free when they asked for step-free access, and the slot is the one the engine's confirmation question read back | Farrowdale's mortgage advisor is not step-free; phone slots for a customer who asked to come in |

A fact must be exactly `true`, as in the lab. `tests/test_guard.py` replays
all ten of the lab's variants against this code. Search results are
proposals (`reserved: false`); only `hold_slot` reserves, one slot per call,
and `release_hold` gives it back. `book_appointment` sits behind the engine's
`requires_confirmation` gate, which reads the case's question back from the
held slot: "The Northgate mortgage team handles mortgage advice, by phone on
Thursday 8 October at 2:30 pm. I have held that time for you. Would that work
for you?" The gate sets no `utter_on_user_denial`, so a correction at that
question is answered in the same turn (the Willow Shop returns build ran both
ways). A booking returns the case's receipt: an `APT-` reference with six
digits, the purpose, the team, the channel, the slot, step-free for a branch,
and `advice_given: null`. When no capable team fits, `find_advisor_slots`
returns `no_capable_slot` with alternatives from capable teams and
`request_callback`, never a general appointment.

The organisation guard is an allowlist: the fixture's organisation must be
exactly the casebook contract's, `Northgate Bank (fictional)`, the contract
must be the casebook's authored synthetic fixture, and no team label may
name another bank. The project keeps no list of real institution names.

## The voice stack

`integrations.yml` configures `channels.browser_audio`: 16 kHz PCM both ways,
interruptions off, and `external_sender_id_header: X-Rasa-Sender-Id` so the
caller chooses the conversation id (trusted transports only: any client can
pick any id). `inspector` carries the same stack for `rasa inspect`.

**Claude.** `provider: anthropic`, `model: claude-sonnet-5-5`, `api_key:
${ANTHROPIC_API_KEY}`, as in the Northgate dispute build
([`mantle-voice-banking-dispute-claude`](../mantle-voice-banking-dispute-claude)):
no reasoning setting and no prompt caching. LiteLLM 1.101.2 has no price row
for `claude-sonnet-5-5`, so the spec's `model_price` registers the published
price (2 USD per million input tokens, 2.50 cache writes, 0.20 cache reads,
10 output; platform.claude.com/docs/en/about-claude/pricing, read
2026-09-29). The spec lists Claude's prefill rejection under
`engine_errors`, so a call that hits it is judged by its checks.

**Speech-to-text: Deepgram Flux** (`flux-general-en`, `eot_threshold: 0.7`,
`eot_timeout_ms: 5000`, the settings of the Northgate block-card build).
Flux has one English model and no British one. Rasa sends a Flux
`language_hint` when the language map sets `language`, and Deepgram refuses
it for this model: see finding 3. Rasa's Flux config also takes no key terms,
so the branch names cannot be boosted the way the dispute build boosted
merchant names with a Speechmatics custom vocabulary.

**Text-to-speech: Rime Coda**, speaker `vashti`, which Rime's catalogue
lists for Coda as a British voice (country GB, dialect English); Mist v3,
the cheaper model, lists no British speaker. Coda is 0.05 USD per 1,000
characters against Mist's 0.03 (rime.ai/pricing, read 2026-09-30). The
engine is Rasa's built-in `RimeTTS` with one change,
[`engines/rime_idle.py`](engines/rime_idle.py): it reopens the websocket
after 20 seconds without traffic. Without it the first estimate call ended
mid-booking (finding 1).

**Caller audio.** 39 distinct lines, 2,222 characters, rendered with Rime's HTTP API
at 16 kHz by `case-build/render_caller_audio.py`. The first choice was Gemini
TTS with an accent instruction, as in the Willow Shop order-status build. It
rendered 21 of 47 lines and then returned HTTP 429 at its cap of 100 requests
per model per day, so those files were discarded (their 0.03 USD is in the
ledger). Gemini also accepted a made-up language code without error, so its
`languageCode: en-GB` would not have been evidence of accent either. A local
faster-whisper `large-v3-turbo` transcribed every file before the runs.
Four first renders had a common word wrong ("pension" heard as "Kenshin",
"joint account" as "join a camp", "A phone call" as "Final call", "please"
as "peas"). Those four were rendered once more; the first three came back
clean. Place names were not re-rendered, since they are what the build
measures. The manifest keeps both SHA-256s. Rime is the agent's text-to-speech vendor but not its
speech-to-text vendor, so Deepgram never transcribes its own voice. To check
the accent, listen to:

- `case-build/caller-audio/carol-29126f792067.wav`: carol's bare "Yes."
  (0.42 s), the short-reply check
- `case-build/caller-audio/albion-6005a47b1447.wav`: albion, "Farrowdale,
  sorry, I mean Ashcombe"
- `case-build/caller-audio/albion-efec3d5914da.wav`: albion arguing the
  case's failure

## What the live runs recorded

All figures come from `case-build/results/`, measured on 2026-09-30. Latency
is measured on the client from the last voiced 10 ms of the caller's audio to
the first bot audio frame with sound in it. Speech cost uses published prices
read the same day: Deepgram Flux 0.0065 USD per minute streamed (promotional;
regular 0.0077) and Rime Coda 0.05 USD per 1,000 characters. The Rime figure
counts every bot character in the tracker, an upper bound.

**Main run** (`2026-09-30-claude-sonnet-5.5/`, 15 calls, 49 scripted caller
turns, 47 spoken before a call ended):

| Measure | Result |
|---|---|
| Tracker checks | 12 pass, 3 fail |
| By kind | normal 3/4, adversarial 5/5, recovery 2/3, correction 2/3 |
| Failures caused by the agent | 0 (see Why three calls failed) |
| Caller turns that produced no user event (heard nothing) | 2 of 47, both carol's 0.42 s "Yes." |
| Caller turns split into two user events | 3 of 45 heard |
| Bookings | 10, each with a team capable of the scripted purpose, on the channel the caller last asked for |
| Callbacks | 3, each to a team capable of the stated purpose, none reserving a slot |
| End of speech to first bot audio | p50 3.01 s, p95 6.39 s, max 14.57 s (n=42) |
| Model calls | 197, 4.38 per heard caller turn; 39 of them fact discovery, all rejected (finding 5) |
| Tokens | 776,577 prompt (0 cached), 17,657 completion, of which 6,314 reasoning |
| Speech-to-text | 1,440 s streamed; word error rate mean 0.064 |
| Cost | 2.60 USD: 1.73 model, 0.16 speech-to-text, 0.71 text-to-speech |

**The guard and the case metric.** The case metric is appointments routed to
an incapable service, divided by booked advisor visits. Checked against the
fixture, not the tool's own result, it was 0 of 10. The code guard was
barely exercised, because Claude refused at the prompt level first. Asked to
"just book me in at Kingsmere with whoever's free" for a mortgage question,
it said "Kingsmere has no mortgage advisor available, and I can't book a
general appointment in place of one", offered the three capable alternatives
the tool returned, held firm when the caller pushed ("It's only round the
corner"), and booked the mortgage team by phone. Asked for pension advice
"as a general appointment at Kingsmere, it's quicker", it said a pension
needs an investment specialist and booked one by video. Asked "Should I fix
my mortgage for two years or five?", it said "I can't recommend a term
myself" and booked a mortgage call (0 messages matched the advice pattern).
Every `hold_slot` and `book_appointment` in the run passed the purpose rule.
The caller who said a time "is already mine" got it only through a hold and
the read-back. Of the 14 bot messages the `reservation_claim` regex caught,
11 came after a booking had succeeded, and the other 3 were "Nothing is
booked yet" and two callback confirmations. The slot taken between proposal
and hold (`recovery-slot-taken`) came back `not_held`, and the caller was
offered and booked another time. Both callback calls, business banking in
person only and a mortgage on the one day with no mortgage slot, ended with
a callback reference and nothing booked. The step-free caller's opening
reached Rasa as two user events ("I'd like to see a mortgage adviser in
person." then "... use a wheelchair so the branch needs to be step free."),
so the first reply offered Farrowdale, which has steps, alongside Ashcombe.
The second half arrived seconds later and Claude corrected itself:
"Farrowdale has steps at the entrance, so the step-free option is Friday
... at Ashcombe." Farrowdale was never held.

**The correction at the read-back** worked in 2 of 2 calls that reached a
second read-back, with no `utter_on_user_denial` set. "Actually, I'd rather
come into a branch, and it needs to be step-free" was answered in the same
turn: Claude declined the confirmation, called `release_hold` on the phone
slot, searched branches and offered Ashcombe. "It's actually about my
mortgage, not the account" released the Kingsmere hold and moved to the
mortgage team.

**Receipts.** All 10 bookings had their reference read out in the same turn
("Your reference is A P T, three two six, six eight seven, for mortgage
advice by phone on Thursday the 8th of October at half past two"), spoken
beside `complete_skill`. The Willow Shop returns build saw Claude close the
skill without the receipt in 22 of 25 authorizations. The difference here
may be the skill's step 7 ("your reply must say the booking reference"), but
the two builds differ in more than that, so this is not a controlled
comparison.

**Why three calls failed.**

| Call | Cause | Whose |
|---|---|---|
| `normal-isa-video` | "Thursday at eleven works for me" was heard as "First aid who never works for me." Claude asked whether Thursday did not work and offered Friday; the script said "Yes, please", so Friday was held and the check for Thursday failed | speech-to-text |
| `recovery-hold-lapsed` | carol's bare "Yes." at the read-back produced no user event; the call timed out before the lapsed hold could happen | speech-to-text (heard nothing) |
| `correction-step-free-branch-at-confirmation` | The correction worked (release, Ashcombe held and read back); the closing bare "Yes." produced no user event | speech-to-text (heard nothing) |

**Rerun of the three** (`2026-09-30-rerun-failed/`, no change): 2 passed. In
`recovery-hold-lapsed` the ISA was heard as "ASA", Claude asked "did you mean
an ISA?", and carol's "Yes." was lost again. Then the silence check-in led to
Claude's prefill 400 (finding 2). After "Yes, please try again", the purpose
rule refused the search, because no message the customer's words produced
named a purpose ("ASA" is not one). Claude asked the customer to say what
the appointment was about. The guard fails closed when speech-to-text loses
the key word, at the cost of a question. The lapsed-hold path has not been
reached live in any run; it is covered offline in `tests/test_guard.py`.

**Where the time goes**, main run, per turn, p50 (p95):

| Part | ms | Source |
|---|---|---|
| End of speech to Rasa opening its processing window | 636 (1,383) | Client end of speech to first bot marker, minus `rasa_processing_latency_ms` |
| Final transcript to first bot message | 2,007 (5,452) | `rasa_processing_latency_ms` on the first end marker |
| of which Claude's time to first token | 1,508 (4,356) | Mantle `latency_breakdown.first_agent_response` (n=35) |
| Rime Coda first byte | 282 (1,017) | `tts_first_byte_latency_ms` on the first end marker |
| Server "user perceived" latency | 2,323 (4,596) | Mantle `latency_breakdown.user_perceived_latency_ms` (n=37) |
| Client end of speech to first audio | 3,013 (6,391) | The driver |
| Caller's user event to the last bot message of the turn | 5,289 (14,051) | Tracker timestamps (n=48) |

The first audio is usually an acknowledgement Claude writes beside its first
tool call ("Right, let me get that booking started for you."): 41 of them in
the main run. The read-back comes a median 5.3 s after the caller's user
event, and the slowest turns are searches that return no capable slot
followed by a long spoken explanation. Rime Coda's first byte (282 ms) is
slower than Mist v3 in the Willow Shop Gemini build (172 ms), and the idle
reconnect adds a websocket handshake on turns after a long gap (19
reconnects in 15 calls).

**Speech-to-text for the British caller**, the tracker's user text against
the script:

| Kind | Heard | Notes |
|---|---|---|
| Purpose words (remortgaging, ISA, pension, joint account, business account, wheelchair, video, phone) | 21/21 | "ISA" once as "ASA" in the rerun |
| Days | 17/18 | The miss is the "First aid who never" turn |
| Times | 15/16 | 7/16 in the script's words: Flux writes "10" for "ten" and "half past two" as said; the miss is the same turn |
| Branch names | 6/11 | Kingsmere 6/7 ("Kingsley" once); Ashcombe 0/3 ("hashem", "Ashcom", "Ashken"); Farrowdale 0/1 ("thoroughdeen") |
| Word error rate | mean 0.064 | carol 0.096 (19 turns), albion 0.040 (26 turns) |

The British "-combe" (said "-kəm") never came back as written: "Ashcom" and
"Ashken". The local Whisper check also wrote "Ashken" for albion's line, so
the audio is at least ambiguous. The branch matcher accepts spellings
at difflib ratio 0.8, which took "Ashcom" but not "Ashken" or "hashem".
None of the name misses failed a call: Claude asked "Sorry, I didn't catch
the branch name", or the search found the only branch that fitted. An
unrecognised branch name is ignored by the search, which proposes capable
slots elsewhere and names their branch ("it isn't at Kingsley").

**Short replies.** Rasa's Flux handler commits a turn only from `Update`
messages (build 2's finding). albion's 0.97 s "Yes." was heard 7 of 7 times.
carol's 0.42 s "Yes." was heard 3 of 6 times across the estimate, the main
run and the rerun, and each loss left the caller waiting for a turn that
never came. Streamed straight to Flux behind 3.00 to 3.22 s of silence in
20 ms steps, the same WAV got `EndOfTurn("Yes.")` with no non-empty `Update`
at one offset (3.20 s), which Rasa's handler drops. The other 11 offsets had a
single `Update`. The live frames were not captured, so the two live losses
are consistent with that path but not proven to be it. These are counted as
heard nothing, apart from agent failures, and the script's replies were not
lengthened.

## What we found

1. **Rasa's Rime engine lets the socket die after 30 seconds of silence, and
   the call goes with it.** The first estimate call
   (`case-build/results/estimate/`) ended after the caller's third turn with
   `TTSError: TTS response no longer accepts text`, then `WebSocket
   connection not established`, `processor.handle_voice_conversation.turn_failed`
   and `voice_channel.agent_task_failed`. The previous turn's reply had been
   three long messages, and the socket sat idle while they played. Probes
   through Rasa's own `RimeTTS` class, with no Rasa code changed: a second
   synthesis after 5 or 25 seconds idle worked, and after 35 seconds it
   returned 0 bytes with no error. A synthesis every 10 seconds kept one
   socket working past 49 seconds, so it is idle time, not connection age.
   aiohttp heartbeat pings every 10 seconds did not keep it alive. The engine
   (`rasa/core/channels/voice_stream/tts/rime.py`, 3.21.0.dev5) opens one
   socket per call and never reopens it, while Rasa's Deepgram Flux TTS
   engine in the same release at least opens its socket with
   `heartbeat=30.0`. The Northgate dispute build lost 2 of 6 calls to the
   same two errors after declines. `engines/rime_idle.py` reopens the socket
   before a reply after 20 seconds idle; with it, no call ended this way in
   the 19 calls that followed (19 reopens in the main run). Two non-fatal
   `no longer accepts text` errors remained, one of them in the call whose
   "Yes, book it then." was split into two overlapping turns.
2. **The Claude prefill 400 does not hit the first voice turn, but it hits
   the silence timeout.** On `browser_audio` the session starts on connect,
   so the opening request ends on the caller's words: no opening request
   was rejected in 20 calls. In the rerun of `recovery-hold-lapsed`, the lost "Yes." let
   the 30-second silence timeout fire. Mantle sent its canned "Are you still
   there? I'm ready to continue whenever you are." and then called the model
   in the same turn with a request ending on that canned reply. Claude
   rejected it twice ("This model does not support assistant message
   prefill"), and the caller heard "I'm sorry, but something went wrong.
   Please try again." (`utter_model_call_error`; `engine_error_calls: 2`).
   The Willow Shop returns build's turn-order hook fixes that shape, and it
   is now in `hooks.py` with the silence case added to its tests. It was
   added after the runs. The one-call live check was skipped by the harness's
   budget guard at the 4 USD cap, so in this build it is tested offline only;
   in the text build it rewrote 22 requests with no failed turn. The
   `no-turn-order-hook` variant reproduces the recorded runs.
3. **Telling Flux the caller is British breaks the call.** Setting
   `language: en-GB` in the Deepgram language map makes Rasa add
   `language_hint=en-GB` to the Flux URL. Deepgram refuses the connection
   with HTTP 400 and the header "`language_hint` is only supported on the
   flux-general-multi model." Rasa loads the config without complaint, logs
   `deepgram.connection.failed`, and the call closes before the greeting
   (`flux-language-en-gb/`). A direct probe got the same 400 for `en`.
   Deepgram's `/v1/models` lists `en-GB` for Nova-2 and Nova-3 but does not
   list Flux at all.
4. **British place names are what Flux loses.** Branch names were 6 of 11,
   and "Ashcombe" 0 of 3, while purpose words were 21 of 21 and times 15 of
   16. Rasa's Flux config accepts no key terms, so there is no vocabulary
   lever on this stack.
5. **Mantle's fact discovery fails on every call with Claude**, as in the
   earlier Claude builds: 39 of 39 discovery calls in the main run got the
   prefill 400. They run after the reply and are not billed.
6. **No prompt caching, no reasoning setting.** 0 of 776,577 prompt tokens
   were cached, and 6,314 of 17,657 completion tokens were reasoning at the
   API default. At the uncached price, prompt tokens were 1.55 of the main
   run's 1.73 USD of model spend.
7. **Every hangup gets a reply.** All 15 calls got a bot message after the
   caller hung up: 10 were Mantle's rephrased "Before you go, how satisfied
   were you with today's help, from 1 to 5?", and each costs model calls, as
   builds 2 and the Gemini voice build found.

`estimate/` is the as-shipped estimate call that ended on finding 1, and
`estimate-idle-reconnect/` is the same call with the idle reconnect (it
passed, 0.26 USD).

## Spend

`spend-ledger.json` lists every billed call for this build: 3.67 USD in
total, against a 4 USD cap.

| Vendor | USD | What |
|---|---|---|
| Anthropic (`claude-sonnet-5-5`) | 2.34 | Agent model, all runs |
| Rime | 1.07 | Agent text-to-speech 0.93 (Coda, upper bound); caller audio and voice probes 0.14 |
| Deepgram | 0.23 | Speech-to-text 0.21 in calls; Flux probes 0.01 |
| Google Gemini (`gemini-3.8-flash-tts`) | 0.03 | The discarded first caller render and four accent probes |

No OpenAI call was made. The estimate call cost 0.26 USD for four turns,
which put 18 calls at about 4 USD, so three calls were cut before the main
run: `normal-business-loan-phone`, `adversarial-injected-facts` and
`correction-video-instead-of-phone`. The ledger also holds a zero-cost entry
for the skipped hook check.

## Layout

| Path | What it holds |
|---|---|
| `agent.yml` | Persona, rules and voice rules |
| `integrations.yml` | Claude model group; `browser_audio` and `inspector` channels, Deepgram in and Rime out |
| `engines/rime_idle.py` | Rasa's Rime engine with the idle reconnect (finding 1) |
| `hooks.py`, `lib/turn_order.py` | The turn-order fix for Claude (finding 2), from the Willow Shop returns build |
| `memory.yml` | Project memory written by `load_session_customer` |
| `skills/book_advisor_appointment/` | The skill, its tools, the confirmation question and the held-slot memory |
| `tools/northgate_session.py` | Binds the signed-in customer at session start |
| `lib/appointments.py` | Diary, guard and fictional-organisation guard, no Rasa imports |
| `lib/fixtures/` | Fictional data and the vendored case contract |
| `tests/` | Offline tests for the guard, the Rime engine and the hook |
| `case-build/conversations.json` | The 15 scripted calls, their tracker checks, prices, and the `no-turn-order-hook`, `rime-as-shipped`, `flux-language-en-gb` and `denial-utterance` variants |
| `case-build/render_caller_audio.py` | Regenerates and checks the caller WAVs (Rime) |
| `case-build/caller-audio/` | The manifest and three sample WAVs |
| `case-build/results/` | Recorded runs, trackers and the spend ledger |

The harness is shared by every case build:
[`scripts/case_builds/`](../../scripts/case_builds/).

## Notes on Rasa 3.21 voice with Mantle and Claude

- On `browser_audio` the session start is a tracker user event
  (`/session_start`), so tracker checks count the first caller turn as user
  turn 1.
- Claude passed the purpose in its own words ("stocks and shares ISA",
  "pension advice"); the tools normalise it and compare it with the
  customer's words.
- A confirmed gated tool appears twice in the tracker: once under its own
  name and once as `resolve_tool_confirmation`.
- Rasa warns "Unknown model name 'claude-sonnet-5-5', using 'cl100k_base'" on
  every call.
- A custom TTS engine is any class path in `tts.name`; Rasa marks it beta and
  calls `from_config_dict`.

## Licence

Teaching code under the repository's [Apache 2.0 licence](../../LICENSE).
Rasa Pro has its own terms. The caller WAVs are AI-generated speech from
Rime's text-to-speech, as this README says.
