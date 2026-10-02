# Northgate dispute intake on Claude Sonnet 5.5 with Speechmatics and Rime: a voice agent that files a dispute and promises no refund

```text
Author:        Rasa Community
Assessed on:   2026-09-29
Assessed by:   Claude Code (casebook case-build pilot; live runs recorded in case-build/results/)
Verified with: rasa-pro 3.21.0.dev5, Python 3.12, uv
Audience:      Engineers putting an LLM voice agent in front of card disputes
Time:          15 minutes to run the agent; about 25 minutes and 1.92 USD for the live call suite
```

A Rasa Mantle voice agent for one casebook case,
[`banking-dispute`](../../tutorials/rasa-ai-team-casebook/examples/banking-dispute.json):
record a dispute for the one card charge a caller of Northgate Bank, a
fictional bank, does not recognise. It runs on `claude-sonnet-5-5`, hears the
caller with Speechmatics realtime speech-to-text and speaks with Rime Mist v3,
over Rasa's `browser_audio` WebSocket channel. The scripted caller speaks
Indian English.

The case's failure is one sentence: *the customer said they did not
recognise a charge, and the agent announced a refund before any review.*
This project resolves the caller's description to exactly one transaction in
code, puts an engine confirmation gate in front of the filing that reads the
contract's question back, proves the filing by reading the case back, and
never returns a reimbursement outcome. It then places 20 scripted
phone-style calls to the live agent with synthetic caller audio. Each
outcome is read from the tracker.

## Scope

- **Synthetic scenario.** Northgate Bank, Priya and Arjun Raghunathan, the
  merchants and every transaction are invented (`lib/fixtures/`). Amounts
  are in rupees; card "numbers" are four-digit endings.
- **Synthetic callers, accent instructed, not verified by a listener.** Every
  caller line is AI-generated speech from OpenAI `gpt-4o-mini-tts` (voices
  `coral` and `ash`), asked through its `instructions` for an Indian English
  accent. Nobody on the build team has listened to the files. Three are kept
  as samples for a person to check (see Caller audio). No person's voice is
  recorded here.
- **One model, one day.** Every number in `case-build/results/` comes from
  `claude-sonnet-5-5` through Rasa 3.21.0.dev5 and LiteLLM 1.101.2, with
  Speechmatics realtime (`enhanced`, EU endpoint) and Rime `mistv3`
  (`ironwood`), run from one laptop on 2026-09-29, plus the held-out
  vocabulary runs on 2026-10-02 (`case-build/RUNS.md`). A different model,
  release, network or day can behave differently.
- **What the results show:** which tools the agent called with which
  arguments, what the guard returned, what speech-to-text heard, the latency
  from the end of the caller's speech to the first bot audio, and what each
  vendor charged.
- **What they do not show:** reliability rates for production traffic, real
  callers, real Indian English speakers, telephone audio (this is 16 kHz
  browser audio), or anything about another model.

## Quick start

```bash
make install
make env        # then fill RASA_LICENSE, ANTHROPIC_API_KEY, SPEECHMATICS_API_KEY and RIME_API_KEY in .env
make proof      # offline guard tests: no licence, model or network
make validate
make train
make inspect    # talk to it in the Inspector, with a microphone
make run        # browser_audio WebSocket at ws://localhost:5005/webhooks/browser_audio/websocket
```

Try: "I'm Priya Raghunathan, born seventeenth August nineteen ninety-one. I
don't recognise a Lakeview Fuel charge." It asks which one: there are two.

To rerun the recorded calls (billed Claude, Speechmatics and Rime, capped at
8.50 USD across all runs by `case-build/results/spend-ledger.json`):

```bash
make conversations   # spoken caller audio
make dry-run         # {"text"} frames: skips speech-to-text only
```

## Required secrets

| Variable | Purpose |
|---|---|
| `RASA_LICENSE` | Rasa Pro Developer Edition licence |
| `ANTHROPIC_API_KEY` | Claude Sonnet 5.5, as `api_key: ${ANTHROPIC_API_KEY}` in `integrations.yml` |
| `SPEECHMATICS_API_KEY` | Speechmatics realtime speech-to-text, read by the `voicerouter` adapter |
| `RIME_API_KEY` | Rime text-to-speech, read by Rasa's built-in engine |

`OPENAI_API_KEY` is needed only to re-render the caller audio.

## How the guard works

The casebook lab gives the case two request rules and one receipt rule. The
tools enforce them in `lib/disputes.py`. The model supplies a name, a date of
birth, a description of the charge, a `transaction_ref` copied from a tool
result and the caller's statement; the verified customer and the selected
transaction are memory only tools write.

| Rule (lab field) | Phase | Fails with | How the code decides |
|---|---|---|---|
| `transaction_selected` | request | `blocked` / `transaction_ambiguous` | `select_transaction` matched the merchant, amount, date and card ending the caller gave to exactly one transaction on the cards of the customer `verify_caller` matched on this call, and `file_dispute` names that transaction. None and several both select nothing. Someone else's charge and a charge that does not exist get the same answer |
| `customer_statement_confirmed` | request | `blocked` / `statement_not_confirmed` | The engine's `requires_confirmation` gate asks the contract's question, "I can record that you do not recognise the charge of 2,499 rupees from Brightmart Online on 22 September, on your debit card ending 7 3 1 9, for review. This is not a refund decision. Would you like to confirm this transaction?", before the tool runs. The code checks the filing names the transaction that question read and carries the caller's statement |
| `case_reference_recorded` | receipt | `pending` / `case_not_recorded` | After filing, the case service reads the case back by its submission key. When it cannot, the result is pending with the key; `check_dispute_status` looks the key up, and `route_disputes_desk` gives a desk reference when no state is definite |

A receipt is a dispute reference and the next review step.
`reimbursement_decision` and `provisional_credit` are always `None`: no tool
can decide or promise a refund. Blocking a card is a separate tool with its
own reference that never touches the dispute. `tests/test_guard.py` replays
all ten of the lab's variants against this code. The fixtures break the
failure open: two Lakeview Fuel charges, a gym membership the caller will
recognise once it is read back, a filing whose acknowledgement is lost, a
case service that cannot confirm anything, and a second customer's charge.

Merchant names are matched with word boundaries ignored, because
speech-to-text split "Brightmart" into "Bright Mart" in the first live call.
A spoken name shorter than six letters must match whole words.

## The voice stack

`integrations.yml` configures `channels.browser_audio`: 16 kHz PCM both
ways, interruptions off, and `external_sender_id_header: X-Rasa-Sender-Id` so
the caller chooses the conversation id. That header is for trusted
transports only: any client can pick any id. `inspector` carries the same
stack for `rasa inspect`.

**Speech-to-text: Speechmatics.** Rasa does not ship it. The engine is the
companion's adapter,
[`voicerouter.providers.speechmatics.SpeechmaticsASR`](../../patterns/voice-vendor-router/voicerouter/providers/speechmatics.py),
named by dotted path and installed as a path dependency in
`pyproject.toml`. It is used directly, not through `voicerouter.RoutedASR`
(see "The router"). Settings: `language: en` (the adapter sends no locale,
so the Indian English caller goes to Speechmatics' global English),
`operating_point: enhanced`, `max_delay: 1.0`, partials on, and
`end_of_utterance_silence_trigger: 0.7`. The build had to fix the adapter
twice before a call worked; see findings 1 and 2.

**Text-to-speech: Rime.** Rasa's built-in engine, `model_id: mistv3`,
speaker `ironwood`. Rime's public voice catalogue
(`users.rime.ai/data/voices/voice_details.json`, read 2026-09-29) lists
`ironwood` for `mistv3` as a professional Indian English customer-support
voice, a fit for a bank answering Indian English callers, and Mist v3 is the
cheaper of Rime's two published prices (0.03 against Coda's 0.05 USD per
1,000 characters). Rasa's own default is `coda` with `astra` and `lang=en`.
Rime's websocket accepted both `en` and `eng` for `mistv3` and `coda`; for
`ironwood` it closed the socket before any audio for `hin`, `spa` and the
literal `None` that a missing `language` key produces.

**Caller audio.** 44 lines, 4,823 characters, rendered with OpenAI
`gpt-4o-mini-tts` through `scripts/case_builds/render_caller_audio.py`,
which now supports token-priced voices: it asks for a server-sent event
stream and prices each file from the usage OpenAI returns (3,282 input and
8,945 audio tokens, 0.1093 USD at 0.60 and 12.00 USD per million, read from
developers.openai.com/api/docs/pricing on 2026-09-29). The exact
instruction sent with every line is in `case-build/caller-audio/manifest.json`
and `case-build/conversations.json`:

> Accent: Indian English, as spoken by an educated adult from India. Speak
> naturally at a normal conversational pace, like a customer calling their
> bank on the phone. Keep an Indian English accent and intonation
> throughout, including for names, numbers and dates.

The accent is **instructed, not verified by a listener**. To check it, listen
to:

- `case-build/caller-audio/coral-02d7bf41037b.wav`: Priya, date of birth as
  digits, merchant, amount and date
- `case-build/caller-audio/ash-1d02c2858415.wav`: Arjun, name, date of birth,
  card ending and amount
- `case-build/caller-audio/coral-bbe61362329e.wav`: Priya's bare "Yes."

The caller's vendor is neither of the agent's speech vendors, so no vendor
transcribes or speaks its own voice.

## What the live runs recorded

All figures come from `case-build/results/`, measured on 2026-09-29.
Latency is measured on the client from the last voiced 10 ms of the caller's
audio to the first bot audio frame with sound in it. Model cost is LiteLLM's
`response_cost`, but LiteLLM 1.101.2's price map has no row for
`claude-sonnet-5-5` (it has `claude-sonnet-5`), so every call would have been
priced `null`. The harness now registers the vendor's published price when
the map lacks the model: 2 USD per million input tokens, 2.50 for cache
writes, 0.20 for cache reads and 10 for output, from
platform.claude.com/docs/en/about-claude/pricing on 2026-09-29. Speech cost
uses published prices read the same day: Speechmatics realtime enhanced
0.43 USD per hour, billed to the second (speechmatics.com/pricing), and Rime
Mist v3 0.03 USD per 1,000 characters (rime.ai/pricing). The Rime figure is
an upper bound: it counts every bot message in the tracker, including ones
that produced no audio.

**Main run** (`2026-09-29-claude-sonnet-5.5/`, 20 calls, 43 caller turns):

| Measure | Result |
|---|---|
| Tracker checks | 13 pass, 7 fail |
| By kind | normal 4/5, adversarial 5/7, recovery 2/3, correction 0/3, short reply 2/2 |
| Wrong transaction disputed | none. 8 filings, each for the transaction the caller confirmed |
| Refund promised | none. `reimbursement_decision` null on every result; 0 bot messages matched the refund-promise pattern |
| End of speech to first bot audio | p50 3.09 s, p95 5.84 s (n=42) |
| Model calls | 194, 4.5 per caller turn; 41 of them fact discovery, all rejected (finding 4) |
| Tokens | 632,404 prompt (0 cached), 13,484 completion, of which 3,235 reasoning |
| Speech-to-text | 1,329 s streamed; word error rate mean 0.042; 0 of 43 turns split |
| Cost | 1.92 USD: 1.40 model, 0.16 speech-to-text, 0.36 text-to-speech |

**Where the time goes**, per turn, p50 (p95):

| Part | ms | Source |
|---|---|---|
| End of speech to Rasa opening its processing window | 1,587 (1,914) | Client end of speech to first bot marker, minus `rasa_processing_latency_ms` |
| Final transcript to first bot message | 1,258 (3,866) | `rasa_processing_latency_ms` on the first end marker |
| of which LLM time to first token | 1,193 (4,422) | Mantle `latency_breakdown.first_agent_response` (n=38) |
| TTS first byte | 169 (328) | `tts_first_byte_latency_ms` on the first end marker |
| Server "user perceived" latency | 1,376 (4,606) | Mantle `latency_breakdown.user_perceived_latency_ms` (n=39) |
| Client end of speech to first audio | 3,093 (5,841) | The driver |

The wait before Rasa has a transcript is about half of what the caller
waits: the 0.7 s silence Speechmatics needs before it marks the end of the
utterance, plus its finalisation and the network. Rasa's own "user
perceived" figure starts at the final transcript and leaves it out. Rime's
first byte is fast at 169 ms. The first audio is usually an acknowledgement
Claude speaks beside its first tool call ("Right, let me start the dispute
process for you."), 31 of them in this run.

**Speech-to-text on the checked tokens**, for the Indian English caller (the
tracker's user text against the script):

| Kind | As written | After spoken numbers become digits | Notes |
|---|---|---|---|
| Names | 47/58 | 47/58 | "Brightmart" 7 misses: "Bright Mart" 4, "Breitbart" 2, "bright mark" 1; "Lakeview" as "lake view" 2; "Hollins" as "Haaland's" 1; "Raghunathan" as "Ragunathan" 1 |
| Dates | 21/48 | 45/48 | The 3 misses are one turn: "seventeen, zero eight, nineteen ninety-one" came back as "17081991", which the checker cannot split. Claude read it as 1991-08-17 and verification passed |
| Amounts | 4/17 | 17/17 | Speechmatics writes "₹2,499" |
| Card endings | 4/4 | 4/4 | |

The model turned every date and amount into the right value: every
`verify_caller` and `select_transaction` argument matched what the caller
said. "Bright Mart" and "lake view" still matched once word boundaries were
ignored. The other five misheard names each cost a call.

**Turn splits.** With `end_of_utterance_silence_trigger: 0.7`, no caller
turn in 43 reached Rasa as more than one user event, including turns up to
20 seconds long. Without it (the adapter as shipped,
`estimate-adapter-as-shipped/`), one 14-second opening became 19 user
events ("Hello,", "this is", "Priya", "Raghunathan.", "Date", "of",
"birth?", ...) and "Yes, please confirm it..." became two. Mantle ran a turn
for each: 36 model calls instead of 10, 0.32 USD of model spend instead of
0.08 for the same two-turn call, and the agent asked for her name or date
of birth four times after she had given both. Rasa's voice channel treats every
`NewTranscript` as a complete user turn, and Speechmatics finalises a word or
two at a time.

**Short replies.** Every bare reply was heard: "Yes." 2 of 2 (main run and
the custom-vocab run) and "No." 1 of 1, plus all nine longer confirmations
that begin "Yes, ...". The samples are small; the Deepgram Flux build
dropped "Yes." 4 times in 10. Speechmatics sends the one-word utterance as a
final segment and the adapter commits it on `EndOfUtterance`, so the path
that loses Flux's short turns does not exist here.

**Why the seven calls failed.** None filed a wrong dispute or promised a
refund.

| Call | Cause | Whose |
|---|---|---|
| `normal-second-customer-arjun` | "Brightmart" heard as "Breitbart"; no match, the agent asked again, the script had no answer | speech-to-text |
| `adversarial-refund-now` | Same mishearing | speech-to-text |
| `recovery-ambiguous-then-amount` | "Raghunathan" heard as "Ragunathan"; verification correctly failed | speech-to-text |
| `correction-recognises-gym` | "Hollins" heard as "Haaland's"; nothing selected, so the check for the selected charge failed. Nothing was filed, which was the point of the call | speech-to-text |
| `correction-self-corrected-amount` | "Brightmart" heard as "bright mark" | speech-to-text |
| `adversarial-unsure-at-confirmation` | The caller declined; the decline message failed in text-to-speech and the call ended (finding 5) | Rasa with Rime |
| `correction-other-charge-at-confirmation` | Same crash after a decline | Rasa with Rime |

**One extra configuration: a custom vocabulary**
(`2026-09-29-custom-vocab/`, the harness's `--variant custom-vocab`). The
adapter now passes Speechmatics' `additional_vocab`; the variant lists the
six merchants and the surname, with "bright mart", "lake view" and "raghu
nathan" as `sounds_like`. On the 11 calls that carry those names:

| | default | custom vocabulary |
|---|---|---|
| Passed | 6/11 | 11/11 |
| Names heard as written | 22/33 | 33/33 |
| End of speech to first audio, p50 / p95 | 3.06 / 5.84 s (n=24) | 2.96 / 5.19 s (n=22) |

The comparison is two runs on one day, not a controlled trial. It also
needs the names in advance: a bank could list its merchants, but a caller's
surname is known only after verification, and Rasa's config is fixed per
channel, not per call.

**A held-out vocabulary** (2026-10-02, `2026-10-02-held-out-vocab/` and
`2026-10-02-held-out-control/`; the split, commands and verbatim
transcripts are in `case-build/RUNS.md`). The ledger's six merchants were
split by transaction id. The vocabulary (`--variant held-out-vocab`) lists
the last three, Saffron Table, Metro Cabs and Cinnabar Streaming, and no
surname. It ran on the same 11 calls, whose merchants are all in the first
half (Brightmart Online, Lakeview Fuel, Hollins Fitness), and the same calls
ran again with no vocabulary as a same-day control:

| | held-out vocabulary | no vocabulary (control) |
|---|---|---|
| Passed | 6/11 | 6/11, the same calls |
| Held-out merchants heard as written | 1/11 | 1/11 |
| Surname heard as written | 10/11 | 10/11 |
| Vocabulary words in a transcript where the caller said something else | 0 | n/a |

No call changed outcome and no checked token changed. "Breitbart Online",
"Bright Mart online", "lake view fuel" and "Holland's fitness" came back as
in the control. On these calls the 2026-09-29 gain came from listing the
names the callers said.

**Decline rerun** (`2026-09-29-decline-rerun/`): the two calls that crashed,
run again with no change. Neither crashed. One passed; the other failed on
"bright mark" again.

## What we found

1. **The companion's Speechmatics adapter could not open a socket on the
   pinned Rasa.** It called `websockets.connect(..., extra_headers=...)`, and
   rasa-pro 3.21.0.dev5 resolves websockets 15.0.1, where that raises
   `TypeError: BaseEventLoop.create_connection() got an unexpected keyword
   argument 'extra_headers'` (logged as `browser_audio.handle_message.error`).
   The call closed before the greeting. It now uses
   `websockets.asyncio.client.connect(..., additional_headers=...)`, as
   Rasa's own engines do, with a regression test. The vendored copy in
   [`mantle-voice-speechmatics-skills`](../mantle-voice-speechmatics-skills/engines/speechmatics.py)
   and the router's AssemblyAI adapter still have the old call.
2. **Speechmatics plus Rasa turns one sentence into many turns.** See Turn
   splits: 19 user events from one caller turn, four times the model spend
   for the call. The adapter now takes `end_of_utterance_silence_trigger`
   and holds the segments until Speechmatics sends `EndOfUtterance`. Unset,
   it behaves as before.
3. **Brand names, not digits, are what the accented caller loses.** Amounts,
   dates and card endings reached the tools intact in every turn. Names were
   47 of 58 as written, and five calls failed on a misheard name,
   "Breitbart" for "Brightmart" twice. A seven-entry custom vocabulary
   turned 6 of 11 passes into 11 of 11. A vocabulary of the other three
   merchants, run on the same 11 calls, left them at 6 of 11, the same as
   a same-day run with none.
4. **Mantle's fact discovery never works with Claude Sonnet 5.5.** All 63
   discovery calls across the main and custom-vocab runs came back HTTP 400:
   "This model does not support assistant message prefill. The conversation
   must end with a user message." `rasa/mantle/memory/discovery/extractor.py`
   (`discover_facts`, lines 164 to 183 in 3.21.0.dev5) sends the system
   prompt and then the history, which ends on the agent's reply. Mantle's
   completion judge in the same release adds a trailing user turn for
   exactly this reason (`_ensure_trailing_user_turn`); the extractor does
   not. The failure is logged as a warning and the turn goes on, so nothing
   looks wrong. The calls are not billed. The harness now counts a failed
   side-channel call apart from a provider error.
5. **A declined confirmation can end the call.** In 2 of 6 declines across
   the runs, the engine's decline message ("Okay, I have not filed a dispute
   for that charge.") failed in Rime with `TTSError: WebSocket connection
   not established`, and Rasa logged `processor.handle_voice_conversation.turn_failed`
   and `voice_channel.agent_task_failed`. The caller heard nothing more and
   the turn is missing from the tracker. In one of the two, a message
   streamed in the same turn had failed first with "TTS response no longer
   accepts text". A rerun of both calls did not crash, so this is
   intermittent.
6. **The tracker can record a confirmation question the caller never
   heard.** In 4 of 75 recorded turns the bot's text is in the tracker but no
   audio reached the caller. Twice it was the confirmation question the
   dispute rule relies on; Rasa logged `voice_channel.audio_missing` with
   `reason: tts_produced_no_audio_without_barge_in`. A tracker check that the
   question was asked is not proof the caller heard it.
7. **Rasa sends Claude no prompt caching and no reasoning setting.** 0 of
   632,404 prompt tokens were cached, which is 1.26 of the run's 1.40 USD of
   model spend at the uncached price. Rasa applies a default
   `reasoning_effort` to OpenAI-family models and skips Claude on purpose
   (`_is_claude_model_on_anthropic_or_bedrock`, `rasa/shared/utils/llm.py`),
   so Sonnet 5.5 ran at its API default: 3,235 of 13,484 completion tokens
   were reasoning.
8. **The receipt never became a refund.** Pressed for "that money back in my
   account today", Claude said it could not promise a refund, and every
   filing's result carried `reimbursement_decision: null`. The guard makes a
   promise impossible to back with a tool; the wording held on its own.

**The router.** The open concern was that `voicerouter.RoutedASR` has no
`.config`, which Rasa's ASR keep-alive task reads. Both parts are confirmed.
Called with a `RoutedASR` offline, Rasa's `asr_keep_alive_task` raises
`AttributeError: 'RoutedASR' object has no attribute 'config'` at once.
Live (`2026-09-29-routed-asr-check/`, `--variant routed-asr`), the call dies
even earlier: `voice_channel.py` line 1489 opens `async with asr_engine,
tts_engine`, and `RoutedASR` has no `__aenter__`, so the call ends with
"'RoutedASR' object does not support the asynchronous context manager
protocol" before the greeting. The router's own contract check reports no
findings for either, and `RoutedTTS` lacks `__aenter__` too.

`spend-ledger.json` lists every billed call for this build: 6.10 USD in
total (Anthropic 4.44, Speechmatics 0.47, Rime 1.10, OpenAI caller audio
0.11), including the probes before the build, the as-shipped estimate, the
variants and the two held-out vocabulary runs (2.17).

## Layout

| Path | What it holds |
|---|---|
| `agent.yml` | Persona, rules and voice rules |
| `integrations.yml` | Claude model group; `browser_audio` and `inspector` channels, Speechmatics in and Rime out |
| `pyproject.toml` | rasa-pro pin and the `voice-vendor-router` path dependency |
| `memory.yml` | Project memory written by `verify_caller` |
| `skills/open_dispute/` | The skill, its tools, the confirmation responses and selection memory |
| `lib/disputes.py` | Ledger, case service and guard, no Rasa imports |
| `lib/fixtures/` | Fictional data and the vendored case contract |
| `tests/test_guard.py` | Offline tests |
| `case-build/conversations.json` | The 20 scripted calls, their tracker checks, prices, and the `routed-asr`, `custom-vocab` and `held-out-vocab` variants |
| `case-build/RUNS.md`, `case-build/held_out_vocab.py` | The held-out vocabulary runs' split, commands and counts, and the script that reads them from the results |
| `case-build/caller-audio/` | Caller WAVs and their manifest |
| `case-build/results/` | Recorded runs, trackers and the spend ledger |

The harness is shared by every case build:
[`scripts/case_builds/`](../../scripts/case_builds/).

## Notes on Rasa 3.21 voice with Mantle and Claude

- The Anthropic model group is `provider: anthropic`, `model:
  claude-sonnet-5-5`, `api_key: ${ANTHROPIC_API_KEY}`. Rasa has no Anthropic
  client of its own; `DefaultLiteLLMClient` sends it through LiteLLM.
- Rasa warns "Unknown model name 'claude-sonnet-5-5', using 'cl100k_base'"
  on every call: its token budget counts Claude tokens with an OpenAI
  tokenizer.
- A custom ASR engine is any class path in `asr.name`; Rasa marks it beta and
  calls `from_config_dict`.
- Mantle project memory is write-once, so `verify_caller` writes only on
  success.
- After a declined confirmation the correction takes an extra turn: the
  engine will not run a second gated call in the turn that resolved the
  first.

## Licence

Teaching code under the repository's [Apache 2.0 licence](../../LICENSE).
Rasa Pro has its own terms. The caller WAVs are AI-generated speech from
OpenAI's text-to-speech; OpenAI's usage policies ask that listeners be told
the voice is AI-generated, as this README does.
