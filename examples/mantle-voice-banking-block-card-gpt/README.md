# Northgate block card on GPT-5.5 with Deepgram: a voice agent that blocks one card

```text
Author:        Rasa Community
Assessed on:   2026-09-29
Assessed by:   Claude Code (casebook case-build pilot; live runs recorded in case-build/results/)
Verified with: rasa-pro 3.21.0.dev5, Python 3.12, uv
Audience:      Engineers putting an LLM voice agent in front of card servicing
Time:          15 minutes to run the agent; about 20 minutes and 2.70 USD for the live call suite
```

A Rasa Mantle voice agent for one casebook case,
[`banking-block-card`](../../tutorials/rasa-ai-team-casebook/examples/banking-block-card.json):
block the one card a caller of Northgate Bank, a fictional bank, names and
confirms. It runs on `gpt-5.5-2026-04-23`, hears the caller with Deepgram
Flux and speaks with Deepgram Aura-2, over Rasa's `browser_audio` WebSocket
channel.

The case's failure is one sentence: *the caller reported one lost card, but
the agent blocked every card on the account.* This project resolves a spoken
card ending to exactly one card in code, puts an engine confirmation gate in
front of the block, proves the block by reading every card back, and then
places 24 scripted phone-style calls to the live agent with synthetic caller
audio. Each outcome is read from the tracker.

## Scope

- **Synthetic scenario.** Northgate Bank, Nadia and Marcus Okafor and their
  cards are invented (`lib/fixtures/`). Card "numbers" are four-digit endings.
- **Synthetic callers.** Every caller line is AI-generated speech (OpenAI
  `tts-1`, voices `nova` and `onyx`), rendered once and replayed byte for
  byte. No person's voice is recorded here.
- **One model, one day.** Every number in `case-build/results/` comes from
  `gpt-5.5-2026-04-23` through Rasa 3.21.0.dev5 and LiteLLM 1.101.2, with
  Deepgram `flux-general-en` and `aura-2-andromeda-en`, run from one laptop on
  2026-09-29. A different model, release, network or day can behave
  differently.
- **What the results show:** which tools the agent called with which
  arguments, what the guard returned, what speech-to-text heard, the latency
  from the end of the caller's speech to the first bot audio, and what each
  vendor charged.
- **What they do not show:** reliability rates for production traffic, real
  callers, telephone audio (this is 16 kHz browser audio), accents other than
  two US English synthetic voices, or anything about another model.

## Quick start

```bash
make install
make env        # then fill RASA_LICENSE, OPENAI_API_KEY and DEEPGRAM_API_KEY in .env
make proof      # offline guard tests: no licence, model or network
make validate
make train
make inspect    # talk to it in the Inspector, with a microphone
make run        # browser_audio WebSocket at ws://localhost:5005/webhooks/browser_audio/websocket
```

Try: "I'm Nadia Okafor, born March fourteenth, nineteen eighty-six. I lost my
debit card." It asks which one: there are two.

To rerun the recorded calls (billed GPT and Deepgram, capped at 5 USD across
all runs by `case-build/results/spend-ledger.json`):

```bash
make conversations   # spoken caller audio
make dry-run         # {"text"} frames: skips speech-to-text only
```

## Required secrets

| Variable | Purpose |
|---|---|
| `RASA_LICENSE` | Rasa Pro Developer Edition licence |
| `OPENAI_API_KEY` | GPT-5.5, as `api_key: ${OPENAI_API_KEY}` in `integrations.yml`; also renders caller audio |
| `DEEPGRAM_API_KEY` | Deepgram speech-to-text and text-to-speech, read by Rasa's built-in engines |

## How the guard works

The casebook lab gives the case two request rules and one receipt rule. The
tools enforce them in `lib/northgate.py`. The model supplies a name, a date
of birth, a card ending and a `card_ref` copied from a tool result; the
verified customer and the selected card are memory only tools write.

| Rule (lab field) | Phase | Fails with | How the code decides |
|---|---|---|---|
| `selected_card_owned` | request | `blocked` / `card_not_owned` | The card belongs to the customer `verify_caller` matched on this call. An unverified call owns nothing. Someone else's card and a card that does not exist get the same answer |
| `single_card_confirmed` | request | `blocked` / `ambiguous_card_selection` | `select_card` resolved the ending (and kind, if given) to exactly one card, and `block_card` names that same card. The engine's `requires_confirmation` gate asks "Do you mean the ... card ending 4 4 1 7? Blocking that card will not replace it or change your other cards." before the tool runs |
| `block_state_read_back` | receipt | `pending` / `block_not_verified` | After the block, the card service reads the card back as `blocked`. Every card is read before and after, and the result counts `unselected_cards_changed` |

`tests/test_guard.py` replays all ten of the lab's variants against this code.
The fixtures are built to break the failure open: two debit cards ("my debit
card" is ambiguous), a debit and a credit card sharing the ending 5502, a
prepaid card the service cannot read back, and a second customer's card.
Blocking never orders a replacement; `order_replacement_card` refuses any
card whose block has not been read back.

## The voice stack

`integrations.yml` configures `channels.browser_audio`: 16 kHz PCM both ways,
Deepgram Flux (`flux-general-en`, `eot_threshold: 0.7`, `eot_timeout_ms:
5000`) and Aura-2 (`aura-2-andromeda-en`), interruptions off, and
`external_sender_id_header: X-Rasa-Sender-Id` so the caller chooses the
conversation id. That header is for trusted transports only: any client can
pick any id. `inspector` carries the same stack for `rasa inspect`.

The calls are placed by the shared harness's voice driver
([`scripts/case_builds/voice_driver.py`](../../scripts/case_builds/voice_driver.py)).
It streams each caller WAV in real time with silence between turns, plays
the bot's audio on an emulated speaker, acknowledges playback markers as the
audio drains, and ends a bot turn when the tracker has a `bot_turn_ended`
for every new user event.

**Caller audio.** 36 lines, 3,374 characters, rendered with OpenAI `tts-1`
for 0.0506 USD and resampled to 16 kHz with ffmpeg. Caller speech comes from
a different vendor than the agent's Deepgram stack, so no vendor transcribes
its own voice. We chose OpenAI over the local espeak-ng because a neural
voice is a fairer test of speech-to-text on names and digits than a formant
synthesiser, and because `tts-1` is billed per character, so the render
cost is exact. `case-build/caller-audio/manifest.json` lists each file's
text, voice and SHA-256.

## What the live runs recorded

All figures come from `case-build/results/`, measured on 2026-09-29.
Latency is measured on the client from the last voiced 10 ms of the caller's
audio to the first bot audio frame with sound in it. Model cost is LiteLLM
1.101.2's `response_cost` at 5 USD per million input tokens, 0.50 cached and
30 output. Speech cost uses Deepgram's published pay-as-you-go prices, read
from deepgram.com/pricing on 2026-09-29: Flux streaming 0.0065 USD per
minute (a promotional price; the regular price shown is 0.0077) and Aura-2
0.030 USD per 1,000 characters.

**Main run at default settings** (`2026-09-29-gpt-5.5-default/`, 24 calls,
48 caller turns):

| Measure | Result |
|---|---|
| Tracker checks | 17 pass, 7 fail |
| By kind | normal 4/8, adversarial 8/9, recovery 2/4, correction 3/3 |
| Wrong card blocked | none. Unselected cards changed: 0 over 11 block results |
| End of speech to first bot audio | p50 2.17 s, p95 3.00 s; max 30.2 s (a dropped "Yes.", below) |
| Model calls | 225, 4.7 per caller turn; 21 of them after the caller hung up |
| Tokens | 420,516 prompt (39,680 cached, 9%), 8,477 completion, 0 reasoning |
| Speech-to-text | 1,063 s streamed; word error rate mean 0.038 |
| Cost | 2.71 USD: 2.28 model, 0.12 speech-to-text, 0.31 text-to-speech |

**Where the time goes**, per turn, p50 (p95):

| Part | ms | Source |
|---|---|---|
| End of speech to Rasa opening its processing window | 936 (1,460) | Client end of speech to first bot marker, minus `rasa_processing_latency_ms` |
| Final transcript to first bot message | 756 (1,221) | `rasa_processing_latency_ms` on the first end marker |
| of which LLM time to first token | 739 (1,209) | Mantle `latency_breakdown.first_agent_response` |
| TTS first byte | 271 (657) | `tts_first_byte_latency_ms` on the first end marker |
| Server "user perceived" latency | 1,169 (1,736) | Mantle `latency_breakdown.user_perceived_latency_ms` |
| Client end of speech to first audio | 2,167 (2,998) | The driver |

The server's `user_perceived_latency_ms` starts at the final transcript, so
it leaves out the second the caller spends waiting for end-of-turn detection:
about 43% of what the caller waits here. The first audio is usually not the
answer: on voice turns Mantle has the model speak an acknowledgement beside
its first tool call ("Okay, I'll start securing that card now"), 50 of them
in this run. Rasa then inserts at least 2 s of silence before the next
message (`DEFAULT_MIN_DELAY_AFTER_FILLER_BOT_MESSAGES_SECONDS`).

**Speech-to-text on the checked tokens** (the tracker's user text against the
script): 46/46 digit groups (birth dates) and 26/26 card endings, all after
turning spoken numbers into digits. Flux wrote every number as words ("four
four one seven"), so 0 of 72 matched as written digits. The model turned
them into the right digits: all 66 `verify_caller` and `select_card` calls
across the runs carried a date or ending the caller had said. Names: 42/44.
"Okafor" came back as "Cafor" and "Oka for", and in the variant run as
"Cavour" and "Okefor": 4 wrong of 60 checked name tokens, all the surname.

**Why the seven calls failed.** None of them blocked a wrong card.

| Call | Cause | Whose |
|---|---|---|
| `normal-identity-first-then-card` | "Okafor" heard as "Cafor"; the model also *spoke* a tool call (`<functions.activate target_id="block_card" />`) instead of making it | speech-to-text, model |
| `normal-second-customer-marcus` | The model spoke `{"target_id": "block_card"}` as its acknowledgement instead of calling `activate`; the script ran out of turns | model |
| `normal-block-then-asked-replacement` | The model said "I will block that card now" and ended the turn without calling `block_card`; the script fell a turn behind | model |
| `recovery-block-not-read-back` | Said "I'm checking the card status now" and stopped; the check and the urgent-desk route ran only after the caller hung up | model |
| `normal-date-said-numerically` | "Okafor" heard as "Oka for": verification correctly failed | speech-to-text |
| `recovery-verification-retry` | Our bug: Mantle project memory is write-once, and the first `verify_caller` wrote an empty id on a failed attempt, so the corrected retry raised. Then the caller's "Yes." was dropped | ours, then Rasa |
| `adversarial-spouse-card` | The model refused the husband's card before calling `select_card`. The outcome was right; the check wanted the guard to refuse it | ours (check) |

Both of our faults are fixed. `verify_caller` now writes only on success, and
a verified call cannot switch customer. Rerun at default settings
(`2026-09-29-gpt-5.5-default-verify-fix/`), the wrong-then-right date call
passes. The spouse check now accepts either refusal
(`2026-09-29-gpt-5.5-default-fix-rerun/` passes). The recorded main run keeps
its original checks and outcomes.

**One extra configuration: `reasoning_effort: low`**
(`2026-09-29-gpt-5.5-reasoning-low/`, the harness's `--variant
reasoning-low`, nine of the calls, fixed code). Rasa already sends
`reasoning_effort: none` for this model when the project sets nothing
(`rasa/shared/utils/llm.py`, `_apply_default_reasoning_effort`), so the
default run is the lowest effort. On the same nine calls:

| | default (`none`) | `low` |
|---|---|---|
| Passed | 4/9 | 4/9 |
| Failures, by cause | model 3, model and speech 1, our bug 1 | speech 5 (2 misheard names, 3 dropped "Yes.") |
| Tool calls spoken as text | 2 | 0 |
| Announced an action, then ended the turn without it | 2 | 0 |
| End of speech to first audio, heard turns, p50 / p95 | 2.05 / 3.00 s | 2.26 / 2.98 s |
| LLM time to first token p50 / p95 | 716 / 974 ms | 842 / 1,127 ms |
| Reasoning tokens | 0 | 576 |
| Model cost | 0.94 USD | 0.82 USD |

On these nine calls `low` showed none of the model failures and added about
130 ms to the first token. The pass count did not move: speech caused every
failure instead, and three of the five were the dropped "Yes." below.

## What we found

1. **Rasa drops some one-word replies from Deepgram Flux.** A 0.33 s "Yes."
   produced no user event in 4 of 10 attempts across the runs; every longer
   confirmation was heard (17/17). The caller then waited for the 30 s
   silence prompt. Streamed straight to Flux with no Rasa in between, the
   same WAV ended a turn 8 of 8 times, but once in 8 the only transcript
   arrived on `StartOfTurn` and `EndOfTurn`, with no `Update` in between.
   Rasa's `_DeepgramV2.parse_event` (`asr/deepgram/engine.py`, lines 276-291
   in 3.21.0.dev5) clears its buffer on `StartOfTurn`, fills it only from
   `Update`, and on `EndOfTurn` commits the buffer, ignoring the transcript
   that event carries. An empty buffer returns nothing, and no error is
   logged.
2. **At the default reasoning effort, GPT-5.5 sometimes speaks its tool
   calls.** Twice in 48 turns the model wrote the call as text, and Mantle
   sent that text to the caller as the spoken acknowledgement: an XML-like
   `<functions.activate .../>` and a JSON object. Twice more it announced an
   action and ended the turn without the call. Neither behaviour appeared in
   the nine calls at `reasoning_effort: low`.
3. **A hangup costs a model turn.** When the caller closes the socket,
   Mantle runs `/session_end` as a turn. The model kept working (in one call
   it read the card status and "routed" to the urgent desk) to nobody: 21
   calls, 0.17 USD, 7.5% of the run's model spend.
4. **Endpointing is the biggest single wait.** About 0.94 s of the 2.17 s
   median passes before Rasa has a transcript, and Rasa's own "user
   perceived" figure does not include it.
5. **Project memory is write-once.** Writing a project memory field a second
   time raises "already set and cannot be overwritten"
   (`rasa/mantle/memory/manager.py`). Our first `verify_caller` cleared the
   field on a failed attempt and so broke every retry. It is a useful
   property once known: a call verified as one customer cannot become
   another.
6. **After a declined confirmation, the correction takes an extra turn.** The
   engine refuses a second call to the same gated tool in the turn that
   resolved the first ("already resolved this turn"). A caller who says "no,
   the other card" is asked to confirm the new card on the following turn.

`estimate/` is the single call used to price the suite before it, on the
first version of the correction script. `spend-ledger.json` lists every
billed call for this build: 4.16 USD in total (3.40 GPT-5.5, 0.70 Deepgram,
0.05 OpenAI caller audio), including a greeting-only plumbing call and the
direct Flux probes.

## Layout

| Path | What it holds |
|---|---|
| `agent.yml` | Persona, rules and voice rules |
| `integrations.yml` | GPT-5.5 model group; `browser_audio` and `inspector` channels with Deepgram both ways |
| `memory.yml` | Project memory written by `verify_caller` |
| `skills/block_card/` | The skill, its tools, the confirmation responses and selection memory |
| `lib/northgate.py` | Card service and guard, no Rasa imports |
| `lib/fixtures/` | Fictional data and the vendored case contract |
| `tests/test_guard.py` | Offline tests |
| `case-build/conversations.json` | The 24 scripted calls, their tracker checks, speech prices and the `reasoning-low` variant |
| `case-build/caller-audio/` | Caller WAVs and their manifest |
| `case-build/results/` | Recorded runs, trackers and the spend ledger |

The harness is shared by every case build:
[`scripts/case_builds/`](../../scripts/case_builds/).

## Notes on Rasa 3.21 voice with Mantle

- Mantle reads voice channels from `integrations.yml` only.
  `browser_audio` needs `server_url`, `asr` and `tts`; `agent.voice` in
  `agent.yml` is parsed and ignored.
- The handshake names the sample rate; there is no negotiation. Caller audio
  must already be at that rate.
- The session start appears in the tracker as a user event with the text
  `/session_start`, and the hangup as `/session_end`, each with its own
  `bot_turn_ended`.
- Markers sent during the pacing silence after a filler repeat the previous
  message's `latency` object: the TTS timings reset only after pacing.
  `rasa_processing_latency_ms` also repeats on every later message of a turn.
  Use the first end marker of a turn.
- Mantle's `latency_breakdown` carries `user_perceived_latency_ms` and
  `first_agent_response`; `first_voice_response` was never populated.

## Licence

Teaching code under the repository's [Apache 2.0 licence](../../LICENSE).
Rasa Pro has its own terms. The caller WAVs are AI-generated speech from
OpenAI's text-to-speech; OpenAI's usage policies ask that listeners be told
the voice is AI-generated, as this README does.
