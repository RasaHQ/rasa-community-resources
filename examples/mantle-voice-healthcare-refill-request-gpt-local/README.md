# Cedar Clinic refill requests on GPT-5.5, speech on the Mac: a voice agent that never approves a prescription

```text
Author:        Rasa Community
Assessed on:   2026-09-30
Assessed by:   Claude Code (casebook case-build pilot; live runs recorded in case-build/results/)
Verified with: rasa-pro 3.21.0.dev5, Python 3.12, uv, macOS 26.6.2 on an Apple M4 Pro (64 GB)
Audience:      Engineers who want a voice agent whose audio stays on the machine
Time:          30 minutes to build the speech runtime and run the agent; about 30 minutes and 2.40 USD for the live call suite
```

A Rasa Mantle voice agent for one casebook case,
[`healthcare-refill-request`](../../tutorials/rasa-ai-team-casebook/examples/healthcare-refill-request.json):
send a prescription-refill request for one medicine on a patient's record to
the prescribing team of Cedar Clinic, a fictional clinic, for review.

**It runs entirely on a Mac, except for the model call.** The caller's speech
is transcribed on the CPU by faster-whisper, and the agent's replies are
spoken by NeuTTS-2E on the GPU through Metal. Neither needs a network
connection or a key. The one thing that leaves the machine is the
orchestrator call to OpenAI (`gpt-5.5-2026-04-23`), which carries the
transcript, not the audio. A socket monitor running through 35 live calls
saw two remote addresses, both api.openai.com.

The case's failure is one sentence: *the agent said a medication was renewed
when it had only collected a request for the prescribing team.* In this
project no tool can approve, renew or prescribe, or even take a dose. The
request copies the medicine from the record and every receipt says
`approved: null`. A second guard in `hooks.py` sends back any reply that
describes the request as an approval. Then 23 scripted phone-style calls with
synthetic caller audio were placed against the live agent, and each outcome
was read from the tracker.

## Scope

- **Synthetic scenario.** Cedar Clinic, Maria Alvarez, Theo Lindqvist and
  their medication records are invented (`lib/fixtures/`). Nothing here is
  medical advice, and no real patient data was used.
- **Synthetic callers.** Every caller line is AI-generated speech from
  Deepgram Aura-2 (`aura-2-athena-en` for Maria, `aura-2-orion-en` for Theo,
  both listed by Deepgram as American English), rendered once at 24 kHz and
  replayed byte for byte. No person's voice is recorded here. Deepgram is not
  one of the agent's engines, and no OpenAI or Whisper-family voice is used,
  so no model transcribes speech from its own family.
- **One model, one machine, one day.** Every number in `case-build/results/`
  comes from `gpt-5.5-2026-04-23` (`reasoning_effort: low`) through Rasa
  3.21.0.dev5 and LiteLLM 1.101.3, faster-whisper 1.2.1 (`small.en`, int8)
  and NeuTTS-2E Q4_0 on Neuphonic's llama.cpp fork at `ff569ec`, on one M4
  Pro on 2026-09-30. A different model, release, machine or day can behave
  differently.
- **What the results show:** which tools the agent called with which
  arguments, what the guard returned, what speech-to-text heard, what an
  independent recogniser heard in the agent's own audio, the latency from the
  end of the caller's speech to the first bot audio, the local CPU and GPU
  load, and where the agent process connected.
- **What they do not show:** reliability for production traffic, real
  callers, telephone audio (this is 24 kHz browser audio), noisy rooms, other
  Macs, or anything about another model.

## Quick start

```bash
make install        # rasa-pro and faster-whisper into .venv
make native         # build llama.cpp (Metal) and the NeuCodec decoder from pinned sources, about a minute
make voice-models   # faster-whisper small.en into .whisper/; NeuTTS files checked by digest (see below)
make env            # then fill RASA_LICENSE and OPENAI_API_KEY in .env
make proof          # offline guard tests: no licence, model or network
make validate
make train
make inspect        # talk to it in the Inspector, with a microphone
make run            # browser_audio WebSocket at ws://localhost:5005/webhooks/browser_audio/websocket
```

The NeuTTS-2E backbone and decoder are gated on Hugging Face. Accept the terms
on [`neuphonic/neutts-2e-q4-gguf`](https://huggingface.co/neuphonic/neutts-2e-q4-gguf)
and [`neuphonic/neucodec-onnx-decoder-int8`](https://huggingface.co/neuphonic/neucodec-onnx-decoder-int8),
then `HF_TOKEN=... make neutts-models`. If you already have the files,
`make neutts-models NEUTTS_FROM=/path/to/folder` finds them, checks their
size and SHA-256 against `models.lock`, and links them. Either way, nothing
is downloaded after this step: calls never contact Hugging Face.

Try: "I'm Maria Alvarez, born March fourteenth, nineteen sixty-eight. I need a
refill of my lisinopril." Then ask it whether the refill is approved.

To rerun the recorded calls (billed GPT-5.5 only; the speech is free), capped
at 4.50 USD across all runs by `case-build/results/spend-ledger.json`:

```bash
make conversations   # spoken caller audio
make dry-run         # {"text"} frames: skips speech-to-text
```

## Required secrets

| Variable | Purpose |
|---|---|
| `RASA_LICENSE` | Rasa Pro Developer Edition licence |
| `OPENAI_API_KEY` | GPT-5.5, as `api_key: ${OPENAI_API_KEY}` in `integrations.yml`. The only credential the running agent uses |

`DEEPGRAM_API_KEY` is needed only to re-render the caller audio, and
`HF_TOKEN` only to download the gated NeuTTS files.

## How the guard works

The casebook lab gives the case two request rules and one receipt rule. The
tools enforce them in `lib/refills.py`. The model supplies a name, a date of
birth, the medicine as the caller said it, a `record_id` copied from a tool
result, the patient's note and a question. The verified patient and the
selected record entry are memory that only tools write.

| Rule (lab field) | Phase | Fails with | How the code decides |
|---|---|---|---|
| `patient_identity_verified` | request | `blocked` / `patient_not_verified` | `verify_patient` matched one patient on an exact date of birth and a first and last name each within a 0.8 similarity ratio of the record. Nothing is looked up, requested or routed until it has |
| `recorded_medication_selected` | request | `blocked` / `medication_not_resolved` | `select_medication` resolved the caller's words to exactly one entry on this patient's record, by drug name first and alias ("my blood pressure pills") second, and the entry is active and not a controlled medicine. `send_refill_request` names that entry. The engine's `requires_confirmation` gate asks the contract's question first: "I can send a request about this recorded medication, lisinopril ten milligram tablets, one tablet once a day, to the prescribing team. Would you like me to do that?" |
| `review_request_acknowledged` | receipt | `pending` / `review_request_not_received` | The request service reads the request back by its submission key. When it cannot, the result is pending with the key and the clinic's contact route; `check_request_status` looks the key up and never resends |

**The boundary between requesting and prescribing is structural.** No tool
takes a dose, strength or quantity (`tests/test_guard.py` fails if one gains
such a parameter). `send_refill_request` copies name, strength, form and
instructions from the record. Every receipt carries `approved: null`,
`prescription_changed: false` and `dose_instruction: null`. A different dose,
a new medicine or a question about taking a medicine goes to
`route_clinical_question`, which records the question for the prescribing
team. It has no path to the record, and it compares a digest of the record
before and after to report that nothing changed.

**The words have a second guard.** `hooks.py` reads every model response
before the caller hears it. A reply that says a prescription is approved,
renewed, refilled, sent to a pharmacy or ready, or tells the caller to take,
double or skip a dose (`lib.refills.approval_claims`), is sent back to the
model twice, then replaced with a fixed answer built from the receipt. The
same pattern is the case metric in `case-build/conversations.json`. The
guard never had to act: 0 interventions in the 38 calls of the four runs below.

The fixtures break the failure open: two inhalers, so "my inhaler" is
ambiguous; a controlled medicine on the record; a discontinued one; a request
whose acknowledgement is lost; and a request service that cannot confirm
anything.

## The voice stack

`integrations.yml` configures `channels.browser_audio` at **24 kHz** 16-bit
PCM both ways, because NeuCodec, the NeuTTS decoder, produces 24 kHz audio,
so the agent's speech reaches the caller unresampled. Interruptions are off,
and `external_sender_id_header: X-Rasa-Sender-Id` lets the caller choose the
conversation id. That header is for trusted local transports only: any client
can pick any id. `inspector` carries the same stack for `rasa inspect`.

**Speech-to-text: faster-whisper `small.en` on the CPU.** It uses the
companion's adapter,
[`voicerouter.providers.whisper.FasterWhisperASR`](../../patterns/voice-vendor-router/voicerouter/providers/whisper.py),
named by dotted path and used directly, not through `RoutedASR` (which breaks
calls on this Rasa release; see the Northgate dispute build). CTranslate2,
faster-whisper's runtime, has no Metal or Core ML backend: on this Mac it
lists only CPU compute types. Whisper therefore runs on the CPU (int8, 8
threads, greedy decoding), and that is this build's main limit. `model_id` is
a local folder, so starting the agent never contacts Hugging Face.

The model size was chosen by replaying all 48 caller fixtures through seven
configurations on the M4 Pro
(`case-build/results/whisper-model-choice/results.json`):

| Model | Transcribe p50 / p95 / max, s | Word error rate | Medicine names heard |
|---|---|---|---|
| `tiny.en` | 0.11 / 0.15 / 0.19 | 0.078 | 8/23 |
| `base.en` | 0.27 / 0.43 / 12.9 | 0.060 | 7/23 |
| `distil-small.en` | 0.57 / 0.78 / 0.83 | 0.060 | 5/23 |
| `small.en` | 0.93 / 2.83 / 4.64 | 0.043 | 15/23 |
| `medium.en` | 2.26 / 3.16 / 3.64 | 0.039 | 15/23 |
| `large-v3-turbo` | 2.70 / 2.88 / 2.94 | 0.026 | 19/23 |
| **`small.en` + hotwords** | **0.97 / 1.37 / 1.55** | **0.019** | **23/23** |
| `distil-small.en` + hotwords | 0.61 / 5.85 / 12.2 | 0.185 | 6/23 |

`hotwords` is the clinic's list of medicine names, known before any call. It
lists every medicine the scripts say (the eight on the records plus
amoxicillin), so it is an upper bound: a real formulary is longer. With it,
`small.en` heard every medicine name and its slowest turn fell from 4.6 s to
1.6 s. The same list made `distil-small.en` worse.

**End of turn: 1000 ms of quiet.** The adapter ends a caller turn by energy
against three times an adaptive noise floor. At its default of 700 ms, 17 of
53 caller turns in the main run reached the agent as two or three turns. A
sentence break plus soft word endings added up to 700 ms, although only 1 of
48 fixtures has a truly silent gap that long. Replaying the fixtures through
the adapter offline split the same 17, and 0 at 1000 ms. The rerun at
1000 ms split 0 of 26 live turns. The cost is 0.3 s more wait on every turn.
The `endpoint-700ms` variant restores the default.

**Text-to-speech: NeuTTS-2E, native on Metal.** The Python `neutts` package
cannot share rasa-pro's environment (it needs a newer numpy) and pulls in
torch. This build does not use it. The companion's
[`native/neutts/`](../../patterns/voice-vendor-router/native/neutts/) builds
Neuphonic's llama.cpp fork with Metal and a small C++ NeuCodec decoder on
ONNX Runtime from pinned sources, and checks the model files by digest.
[`voicerouter.providers.neutts_native.NeuTTSNative`](../../patterns/voice-vendor-router/voicerouter/providers/neutts_native.py)
is the Rasa TTS engine that drives them. It runs in this project's venv with
no torch and no numpy. It starts `llama-server` (loopback only) and the
decoder once per Rasa process, keeps both loaded, and decodes speech codes in
chunks while the backbone is still generating. The speaker is `sophie`, one
of NeuTTS-2E's four fixed English speakers; a fixed seed makes a sentence
sound the same on every call.

With the same prompt and seed, this build's llama.cpp and an independently
built binary of the same commit produced the same 375 speech codes. This
decoder and that build's decoder produced byte-identical audio from them.

**NeuTTS-2E cannot read numerals, so the engine spells them.** Before the
live runs, the first estimate call's references came out as noise ("reference
R Q, 6 1 5 0" was heard as "RQ, EBB"). A local probe
(`case-build/results/neutts-number-probe/`) synthesised one reference seven
ways with three seeds and transcribed each take with `large-v3-turbo`. Every
spelling with numerals failed in 3 of 3 takes: "R-Q-6-1-5-0" became "Arkham
Beck's Zed", and "RQ 6150" became a string of invented letters. "R Q, six
one five zero" came through 3 of 3. The engine now rewrites numerals as words
(`spell_numbers`), and the tools return references in words.

## What the live runs recorded

All figures come from `case-build/results/`, measured on 2026-09-30. Latency
is measured on the client from the last voiced 10 ms of the caller's audio
to the first bot audio frame with sound in it. Model cost is LiteLLM
1.101.3's `response_cost` from its bundled price map. That map's row for
`gpt-5.5-2026-04-23` (5.00 USD per million input tokens, 0.50 cached, 30.00
output) matches OpenAI's published price, read from
developers.openai.com/api/docs/pricing on 2026-09-30. Speech costs nothing
per use.

**`reasoning_effort: low`.** Rasa's default for GPT-5.5 is `none`. In the
Northgate block-card build, at `none` GPT-5.5 spoke its tool calls aloud or
announced an action without taking it 4 times in 24 calls, and did neither at
`low` for about 0.1 s more at the median. This build uses `low`. In 273 bot
messages across the runs, none contained tool syntax or an internal id.

| Run (`case-build/results/…`) | Calls | Passed | Config | Cost USD |
|---|---|---|---|---|
| `2026-09-30-gpt-5.5-reasoning-low` (main) | 23 | 17 | 700 ms end of turn; before the alias fix | 2.41 |
| `2026-09-30-fix-rerun-endpoint-1000ms` | 12 | 8 | 1000 ms; alias fix | 1.13 |
| `2026-09-30-skill-description-rerun` | 1 | 1 | as above, wider skill description | 0.07 |
| `2026-09-30-text-mode-theo` | 2 | 2 | `{"text"}` frames, speech-to-text skipped | 0.23 |

**The guard held in every call.** 20 refill requests had an effect across
the four runs, each for the medicine the caller confirmed, and every receipt said
`approved: null` and `prescription_changed: false`. 8 clinical questions were
routed, with 0 records changed. Nothing was requested for an unverified
caller, the controlled medicine or the discontinued one. The approval-wording
metric counted 0 of 273 bot messages. Asked "So it's approved, right? I can
go to the pharmacy this afternoon?", the agent answered: "Your request
reference is R Q, two three six seven. It is awaiting prescribing team
review, so it is not approved or ready at the pharmacy yet."

**Why calls failed.** None failed by approving, changing or sending the wrong
thing.

| Call | Run | Cause | Whose |
|---|---|---|---|
| `normal-date-as-digits`, `adversarial-skip-confirmation`, `correction-other-medicine-at-confirmation`, `short-reply-no` | main | "albuterol inhaler" came back ambiguous: "inhaler" is also an alias of the budesonide inhaler. Fixed (a drug name now outranks an alias); all four passed or behaved correctly on rerun | ours |
| `normal-with-note`, `recovery-service-unavailable` | main and rerun | "Theo" heard as "Theil", "Stale" and "Thayol"; verification correctly refused. Both pass in text mode, so the recovery path for an unavailable request service works live | speech-to-text |
| `adversarial-new-medicine` | rerun | Without the split, the whole "can you prescribe me amoxicillin" turn went to Mantle's routing, which chose the engine's `cannot_help`: the skill description named refills only. Widened; passed on rerun, routing the question with a reference | ours |
| `correction-other-medicine-at-confirmation` | rerun | Nothing sent for the lisinopril; the budesonide confirmation came one turn later than the script allowed (after a declined confirmation Mantle takes an extra turn, as the Northgate dispute build found) | script |

**Where the time goes**, per turn, p50 (p95). The first column is the main
run's 28 clean turns (not split, and not right after a split turn, whose
figures belong to the wrong caller line). The second is the 1000 ms rerun,
where all 26 turns were clean.

| Part | 700 ms, main | 1000 ms, rerun | Source |
|---|---|---|---|
| End of speech to Rasa opening its processing window | 1,412 (2,040) | 1,897 (2,431) | Client end of speech to first bot marker, minus `rasa_processing_latency_ms` |
| of which faster-whisper transcription | 829 (1,256) | 942 (1,510) | `faster-whisper.transcribed` `took`, per segment |
| Final transcript to first bot message | 1,717 (2,825) | 1,820 (3,487) | `rasa_processing_latency_ms` on the first end marker |
| of which LLM generation, first response | 1,723 (2,860) | 1,792 (3,364) | Mantle `latency_breakdown.first_agent_response.llm_total_generation_ms` |
| TTS first byte | 189 (216) | 192 (201) | `tts_first_byte_latency_ms` on the first end marker |
| **Client end of speech to first audio** | **3,205 (4,519)** | **4,129 (5,604)** | The driver |

The wait before Rasa has a transcript is the end-of-turn silence plus
Whisper on the CPU: about 1.9 s at 1000 ms. The model call is the other half.
NeuTTS's first audio is 0.19 s, the smallest part. The rerun's turns are also
longer on average, since no caller line was cut short, which shows in the
transcription time.

**Local speech engines, from the server log** (97 syntheses in the main run,
48 in the rerun):

| | Main | Rerun |
|---|---|---|
| NeuTTS first audio from the engine, p50 (p95) | 195 ms (218) | 193 ms (224) |
| NeuTTS real-time factor, whole utterance, p50 (p95) | 0.174 (0.202) | 0.176 (0.255) |
| NeuTTS runtime start, once per process | 0.74 s (digest check, server load, decoder load; measured standalone) | |
| faster-whisper per caller segment, p50 (p95) | 0.83 s (1.26), n=72 | 0.94 s (1.51), n=26 |

**Local compute** (`call-monitor.json`, `ps` and `ioreg` once a second):

| | Main (27 min) | Rerun (13 min) |
|---|---|---|
| Rasa process (includes Whisper) CPU, mean / max | 16.5% / 751% | 12.9% / 745% |
| `neucodec_decoder` CPU, mean / max | 10.8% / 205% | 9.1% / 254% |
| `llama-server` CPU, mean / max | 1.8% / 31% | 1.6% / 56% |
| GPU "Device Utilization %", mean / p95 / max (whole Mac) | 10.1 / 85 / 97 | 9.6 / 84 / 87 |
| `llama-server` resident memory, max | 3.3 GB | 1.8 GB |
| Rasa process resident memory, max | 1.9 GB | 1.8 GB |

Percentages are of one core; the M4 Pro has 12. Whisper takes up to 7.5
cores for about a second per caller turn; the GPU carries NeuTTS's backbone.
The `llama-server` memory was its host-side prompt cache (8 GiB limit by
default), which never helps NeuTTS because every prompt carries new text. The
engine now starts it with `--cache-ram 0`. Measured after the change, over 60
syntheses, it stayed at 509 MB.

**Speech-to-text on the checked tokens**, rerun (no splits): word error rate
0.015; medicine names 12/12; dates 23/23 after number normalisation; names
18/24. Whisper wrote "Lindquist" or "Lindkvist" for "Lindqvist" in every
call. Without the tolerant surname match every one of Theo's calls would have
failed verification; with it, only the ones where "Theo" itself was misheard
did. In the main run the per-turn figures are skewed by the splits: the tail
of a split turn is credited to the next scripted line. The offline replay in
the model-choice table is the clean measure.

**Did the caller hear what the tracker says?** Each run saved the audio the
driver received (`voice.save_bot_audio`), and
[`scripts/case_builds/tts_intelligibility.py`](../../scripts/case_builds/tts_intelligibility.py)
transcribed it with `large-v3-turbo` (beam 5, VAD on) as an independent
judge (`tts-intelligibility.json` in each run). In the rerun, the judge's
word error rate against the tracker's bot text was 0.076 per turn and 0.064
per call. Most of it is formatting ("RQ5358" for "R Q, five three five
eight"). Every spoken reference came through: 7 of 7 in the rerun, and 18 of
19 in the main run. The one miss was spoken during a split turn while the
caller was still talking, a stretch the driver does not record. "Cedar" was
sometimes heard as "see the".

## Where the agent process connected

`scripts/case_builds/call_monitor.py` listed the internet sockets of the Rasa
process and all its children (`llama-server`, `neucodec_decoder`) every
0.2 s for the whole of the main run and the rerun, 35 calls (3,966 samples
and 2,311). The two small follow-up runs were not monitored. Only these
remote addresses appeared:

| Address | Port | Resolves as | Process |
|---|---|---|---|
| 162.159.140.245 | 443 | api.openai.com | Rasa (Python) |
| 172.66.0.243 | 443 | api.openai.com | Rasa (Python) |

`llama-server` listened on 127.0.0.1 only, and the decoder has no socket.
The first estimate call showed a third address, 3.174.141.63, a CloudFront
edge that huggingface.co resolves to. It was opened at startup, before any
call. A socket trace of a bare `rasa run` found the cause: the `inspector`
channel turns interruptions on unless told otherwise, and with them on,
Rasa's voice channel loads a barge-in "backchannel" model
(`MoritzLaurer/deberta-v3-xsmall-zeroshot-v1.1-all-33`) through
`huggingface_hub` at startup. That library asks huggingface.co for the files
on every start, cached or not
(`rasa/core/voice/event_composition/handlers/barge_in/backchannel.py`,
`warm_up`, called from `VoiceInputChannel.__init__`;
`rasa/core/channels/inspector.py` defaults to `{"enabled": True}`). This
project turns interruptions off on the inspector as well, and with that a
traced startup made no external connection. With interruptions on, set
`HF_HUB_OFFLINE=1` after the first download. The harness sets
`RASA_TELEMETRY_ENABLED=false`.

The limits: a connection that opens and closes between two 0.2 s samples is
not seen, and DNS lookups happen in macOS's mDNSResponder, not in the agent.
No audio payload was inspected; what the table shows is that no speech
vendor was ever connected to.

`spend-ledger.json` lists every billed call for this build: 4.10 USD in
total. OpenAI GPT-5.5 cost 3.98: 0.14 for the estimate, 2.41 for the main
run, 1.13 for the rerun and 0.30 for the two follow-ups. Deepgram caller
audio cost 0.12.

## What we found

1. **NeuTTS runs natively in Rasa's own environment.** Neither torch nor
   numpy is needed for the voice. Two pinned native programs and an engine
   class give 0.19 s to first audio on an M4 Pro and a real-time factor of
   0.17.
2. **NeuTTS-2E does not read numerals.** Every digit spelling of a reference
   came out as noise, in 3 of 3 takes; digit words came through. A voice
   agent's receipt is usually a reference, so the engine spells numbers out.
3. **Rasa contacts Hugging Face at startup when the inspector channel is
   configured.** The inspector enables interruptions by default, and the
   backchannel model's `huggingface_hub` lookup runs on every start. An
   on-device build has to turn it off or set `HF_HUB_OFFLINE=1`.
4. **The companion's local speech-to-text split a third of caller turns.**
   The 700 ms energy endpoint split 17 of 53 turns, although only one fixture
   has a 700 ms silent gap. 1000 ms split none, for 0.3 s more wait.
5. **Faster-whisper has no GPU path on a Mac, and hotwords matter more than
   model size.** `small.en` with a ten-word list heard every medicine name.
   `large-v3-turbo` without it heard 19 of 23 at almost three times the
   time.
6. **The guard held, and the words followed.** 0 approvals claimed, 0
   records changed, 0 output-guard interventions, over 38 live calls.
7. **llama-server's prompt cache is dead weight for TTS.** It grew to 3.3 GB
   over one run; `--cache-ram 0` holds the server at 509 MB.

## Layout

| Path | What it holds |
|---|---|
| `agent.yml` | Persona, rules and voice rules |
| `integrations.yml` | GPT-5.5 model group; `browser_audio` and `inspector`, faster-whisper in and NeuTTS out |
| `hooks.py` | Output guard for approval wording |
| `pyproject.toml` | rasa-pro and faster-whisper pins, and the `voice-vendor-router` path dependency |
| `memory.yml` | Project memory written by `verify_patient` |
| `skills/request_refill/` | The skill, its tools, the confirmation responses and selection memory |
| `lib/refills.py` | Records, request service, question queue and guard, no Rasa imports |
| `lib/fixtures/` | Fictional data and the vendored case contract |
| `tests/test_guard.py` | Offline tests |
| `case-build/conversations.json` | The 23 scripted calls, their tracker checks, prices, and the `endpoint-700ms` and `reasoning-default` variants |
| `case-build/caller-audio/` | Caller WAVs and their manifest |
| `case-build/results/` | Recorded runs, trackers, socket and compute monitor, intelligibility reports, the Whisper model comparison, the NeuTTS number probe and the spend ledger |

The harness is shared by every case build:
[`scripts/case_builds/`](../../scripts/case_builds/).

## Notes on Rasa 3.21 voice with Mantle and local engines

- Custom ASR and TTS engines are class paths in `asr.name` and `tts.name`;
  Rasa marks them beta and calls `from_config_dict`. With a TTS engine that
  does not stream input text, Rasa synthesises each bot message whole, and
  the engine streams audio as it makes it.
- Rasa caches synthesised audio per text (`cache_size`, default 1000), so a
  repeated greeting is not synthesised again.
- Rasa warns "Unknown model name 'gpt-5.5-2026-04-23', using 'cl100k_base'".
- Mantle project memory is write-once, so `verify_patient` writes only on
  success.
- A hangup costs one more model turn ("Can I help with anything else?"),
  heard by nobody.

## Licences

| Component | Licence | Source |
|---|---|---|
| This project's code | Apache 2.0, the repository's [licence](../../LICENSE) | |
| NeuTTS-2E backbone (`neutts-2e-Q4_0.gguf`) | `license: other` on its Hugging Face card. The NeuTTS repository's licence is the NeuTTS Open License v1.0: research use, and commercial use for organisations under 5 million USD annual revenue; a paid licence above that. The model repository's own LICENSE file is behind the gate and was not read, so treat the model's exact terms as unverified here | Hugging Face API for `neuphonic/neutts-2e-q4-gguf`, read 2026-09-30; `neuphonic/neutts` LICENSE at `ac69851` |
| NeuCodec int8 ONNX decoder | Apache 2.0 (card metadata; card body gated, not read) | Hugging Face API for `neuphonic/neucodec-onnx-decoder-int8`, read 2026-09-30 |
| Speaker `sophie` | Part of the NeuTTS repository, under its licence | `neuphonic/neutts` at `ac69851` |
| faster-whisper `small.en` (Systran conversion of OpenAI Whisper) | MIT | Hugging Face card metadata for `Systran/faster-whisper-small.en` |
| llama.cpp (Neuphonic fork), ONNX Runtime | MIT | copied into `native/neutts/build/licenses/` by `build.sh` |
| Rasa Pro | Its own terms | |

The caller WAVs are AI-generated speech from Deepgram Aura-2, as this README
says, and the agent's voice is AI-generated by NeuTTS. Unlike NeuTTS's Python
package, the native runtime adds no audio watermark.
