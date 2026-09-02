# Voice vendor router — failover and vendor swapping for Mantle

```text
Author:        Rod Rivera
Assessed on:   2026-09-02
Assessed by:   Rod Rivera
Verified with: rasa-pro 3.20.0.dev6, Python 3.11+, uv
Audience:      Practitioners running voice agents who cannot afford one vendor to be single points of failure
Time:          30–45 minutes
```

Rasa picks **one** ASR and **one** TTS engine per call. If that vendor fails,
Rasa substitutes generated silence for TTS — there is an upstream `TODO` on the
line — and ends the transcript stream at `logger.warning` for ASR. Either way one
vendor blip takes the call with it: the agent goes mute, or goes deaf, and keeps
the line open while it does.

This is a drop-in router that makes those failures survivable, and makes any
vendor usable.

```yaml
# integrations.yml
tts:
  name: voicerouter.RoutedTTS
  providers:
    - name: rime
      language_map: { en: { voice: cove, language: eng } }
      model_id: mistv2
    - name: deepgram
      language_map: { en: { model: aura-2-andromeda-en } }
```

## The idea

> `ASREngine` and `TTSEngine` are interfaces. A router can implement the contract
> it consumes.

Rasa resolves an unrecognised engine `name` as a dotted path, so the router
installs through the documented extension point — **no fork, no core change** —
and works on all nine voice channels, because engine resolution lives on the
shared `VoiceInputChannel`.

The second half matters as much: **the router does not implement a single
vendor.** Every entry under `providers:` is an ordinary Rasa engine config,
handed to Rasa's own `tts_engine_from_config` / `asr_engine_from_config`. So

- every engine Rasa ships works today — `deepgram`, `azure`, `cartesia`, `rime`
- every engine Rasa adds later works with no change here
- every custom engine works, by dotted path

"Swap any vendor" is therefore not a list of adapters this package has to
maintain. It is a property of delegating resolution back to Rasa.

## Vendors

Rasa ships ASR for `azure` and `deepgram`, and TTS for `azure`, `cartesia`,
`deepgram` and `rime`. Those work through the router already, because it
delegates to Rasa's own factories. `voicerouter/providers/` adds the rest.

| Vendor | Role | Dotted path | Key | Status |
|---|---|---|---|---|
| Deepgram | ASR + TTS | `deepgram` *(built-in)* | `DEEPGRAM_API_KEY` | **live-verified** |
| Rime | TTS | `rime` *(built-in)* | `RIME_API_KEY` | **live-verified** |
| OpenAI | TTS | `voicerouter.providers.openai.OpenAITTS` | `OPENAI_API_KEY` | **live-verified** |
| Speechmatics | TTS | `voicerouter.providers.speechmatics.SpeechmaticsTTS` | `SPEECHMATICS_API_KEY` | **live-verified** |
| Speechmatics | ASR | `voicerouter.providers.speechmatics.SpeechmaticsASR` | `SPEECHMATICS_API_KEY` | **live-verified** |
| ElevenLabs | TTS | `voicerouter.providers.elevenlabs.ElevenLabsTTS` | `ELEVENLABS_API_KEY` | config-only — see below |
| AssemblyAI | ASR | `voicerouter.providers.assemblyai.AssemblyAIASR` | `ASSEMBLYAI_API_KEY` | config-only — see below |
| **Vosk** | ASR | `voicerouter.providers.vosk.VoskASR` | **none — local** | **live-verified** |
| **faster-whisper** | ASR | `voicerouter.providers.whisper.FasterWhisperASR` | **none — local** | **live-verified** |
| Neuphonic NeuTTS | TTS | `voicerouter.providers.neuphonic.NeuTTSLocal` | **none — local** | model not run — see below |
| **AWS Polly** | TTS | `voicerouter.providers.aws.PollyTTS` | AWS credential chain | shape-verified — no creds |
| **AWS Transcribe** | ASR | `voicerouter.providers.aws.TranscribeASR` | AWS credential chain | shape-verified — no creds |
| **Google Cloud TTS** | TTS | `voicerouter.providers.google.GoogleTTS` | Application Default Credentials | shape-verified — no creds |
| **Google Cloud STT** | ASR | `voicerouter.providers.google.GoogleSTT` | Application Default Credentials | shape-verified — no creds |
| Azure | ASR + TTS | `azure` *(built-in)* | `AZURE_SPEECH_API_KEY` | not exercised — no key |
| Cartesia | TTS | `cartesia` *(built-in)* | `CARTESIA_API_KEY` | not exercised — no key |

**"Live-verified"** means audio was actually synthesised or transcribed through
that adapter, in this repository, against the vendor's real API.

**"Config-only"** means the adapter is written against the vendor's documented
protocol and its request shape, URL and event mapping are exercised by tests —
but nobody has run it against the live service, because no key was available.
Two things are stated rather than implied: those two adapters are the ones most
likely to have a protocol detail wrong, and the first person with a key finds
out. Give me a key and the row changes.

A copy-pasteable block per vendor lives in [`examples/`](examples).

### The hyperscalers

All three are covered, and each needed a different transport:

| | ASR | TTS | Transport |
|---|---|---|---|
| **Azure** | built-in | built-in | Rasa ships both — nothing to write |
| **AWS** | Transcribe | Polly | event-stream (ASR), sync SDK (TTS) |
| **Google** | STT v2 | Cloud TTS | gRPC (ASR), sync SDK (TTS) |

None of the three speaks plain JSON-over-websocket, which is what Rasa's
built-in engines assume:

- **AWS Transcribe streaming is an AWS event-stream** — binary framing with its
  own headers and CRCs over a SigV4 presigned socket. Hand-rolling that to avoid
  a dependency would be a poor trade, so this uses the `amazon-transcribe` SDK,
  which is asyncio-native and needs no thread bridge.
- **Google STT v2 is gRPC.** The stream is an *iterator of requests* where the
  first message carries the config and audio follows — the same shape as
  Speechmatics' `StartRecognition`, arrived at independently. Audio from Rasa is
  pushed onto a queue feeding that iterator, so a slow network cannot block
  `send_audio_chunks`.
- **Both TTS sides are synchronous SDKs**, so they share
  [`_sdk_tts.py`](voicerouter/providers/_sdk_tts.py), which runs them in a worker
  thread for the same reason NeuTTS needs one: a synchronous call inside an
  async voice loop freezes every other call on the process.

Credentials are deliberately **not** configuration. boto3 resolves the AWS chain
(env, shared config, instance role) and google-cloud-* resolves Application
Default Credentials. Reimplementing SigV4 or the ADC chain to expose an
`api_key` field would be worse in every way.

Two vendor traps encoded rather than documented-and-forgotten:

- **Polly's raw PCM tops out at 16 kHz.** A 24 kHz channel is upsampled
  locally. The adapter *refuses* any other rate outright rather than quietly
  producing wrong-pitch audio.
- **Google's LINEAR16 comes back with a RIFF header** — a WAV file, not raw
  PCM. It is stripped, and the rate declared in the header wins over the rate
  requested, so a vendor silently returning something else cannot become a
  pitch bug.

**Status: shape-verified, not run.** Every SDK parameter these adapters use was
checked against the installed libraries — Polly's `SynthesizeSpeech` members,
Transcribe's `start_stream_transcription` signature, Google's enums and v2
types all confirmed present. No AWS or GCP credentials were available, so
nothing was synthesised or transcribed. Give me either and the rows change.

### Open-source ASR

Every ASR above except these two is a commercial cloud service. These are not:
both are open source, run entirely on the machine, need no API key and no
network, and are **verified live** — unlike NeuTTS, neither is gated and neither
fights Rasa's dependency pins.

| | Vosk | faster-whisper |
|---|---|---|
| Licence | Apache 2.0 | MIT (runtime and weights) |
| Size | ~68 MB (small English) | ~75 MB (`tiny.en`), downloads on first use |
| Streaming | **natively** | batch, made streaming here |
| Partials | yes — 31 on a 4 s utterance | none: a batch model has nothing to emit early |
| Measured | verbatim transcript, 0.4 s load | correct transcript, **0.12 s** to decode 4 s |

```text
said : 'I would like to transfer fifty dollars to my savings account.'
vosk : 'i would like to transfer fifty dollars to my savings account'   (31 partials)
whisper: 'I would like to transfer $50 to my savings account.'
```

Both are true, and the difference is instructive: Vosk transcribes what was
said, Whisper normalises it. If a downstream tool parses amounts, `$50` is
easier; if you are matching a spoken account name, verbatim is safer.

**Vosk is the odd one out, and it matters.** Whisper and its descendants are
batch: they take a finished utterance. Vosk's recogniser is incremental — feed
it audio and it answers either "still going, here is the partial" or "that turn
is finished". That maps straight onto `UserIsSpeaking` / `NewTranscript` with no
VAD and no guessing, which is what a cloud ASR does too. Combined with 68 MB, no
torch and no download gate, it is the most realistic last resort in a chain.

**Batch models get their streaming shape from
[`_local_asr.py`](voicerouter/providers/_local_asr.py).** It buffers audio,
decides where the caller stopped, and transcribes off the event loop:

```text
audio in ──▶ ring buffer ──▶ endpointing ──▶ transcribe(pcm) ──▶ NewTranscript
```

Endpointing is short-time energy against an **adaptive** noise floor rather than
a constant — a fixed threshold that works in an office fails on a car
speakerphone. Deliberately not a neural VAD: that is another model to download
and another thing to be wrong, and the failure mode here is a slightly late turn
rather than a wrong transcript. Adding another offline transcriber is a
`transcribe()` method, not a rewrite.

Both install through one extra, which — unlike NeuTTS — resolves cleanly against
Rasa's numpy pin:

```bash
uv sync --prerelease=allow --extra local-asr   # vosk + faster-whisper
uv sync --prerelease=allow --extra aws         # boto3 + amazon-transcribe
uv sync --prerelease=allow --extra google      # google-cloud-{texttospeech,speech}
```

Each extra was checked with `uv pip compile` against Python 3.12 *before* being
written, and all resolve on `numpy 2.1.3` — which satisfies Rasa's pin.
Syncing without an extra installs none of them.

One packaging trap, found the hard way: **`vosk 0.3.45` publishes no macOS arm64
wheel**, only manylinux and win_amd64. The extra pins `0.3.44`, which does. A
float breaks the install outright on Apple Silicon.

### The local TTS one

[NeuTTS](https://github.com/neuphonic/neutts) runs on the machine. That makes it
the end of the failover chain that cannot go down because someone else's region
did — put it last in `providers:` and the agent has no path to silence at all.
It is the only provider here that the router never skips for want of a key,
because it has none.

Four things are worth knowing before you reach for it, and none of them are
obvious from "it runs locally":

- **The weights are gated.** Every NeuTTS repository on HuggingFace is
  `gated: auto` — including the Apache-2.0 ones. Local at *inference* time,
  authenticated at *download* time: you need an HF token with access accepted.
- **The licences differ by model.** NeuTTS-Air and `neucodec` are Apache 2.0.
  NeuTTS-Nano and NeuTTS-2E are under the *NeuTTS Open License 1.0*, a different
  document. The examples default to the Apache-licensed pair deliberately, and
  no model or reference audio is vendored into this Apache-2.0 catalogue.
- **It cannot share an environment with Rasa.** `rasa-pro` pins
  `numpy>=2.1.3,<2.2.0`; `neutts` requires `numpy>=2.2.6`. No resolution
  satisfies both, so NeuTTS is deliberately *not* declared as an optional
  dependency — doing so makes dependency resolution fail for everyone,
  including CI, whether or not they want local TTS. Two ways round it, below.
- **`torchao` must be pinned to `0.14.0`.** `neucodec` requires `torchtune`,
  and `torchtune 0.6.1` imports `torchao.dtypes.nf4tensor`, which `torchao 0.18`
  removed. Without the pin `import neutts` fails outright. Also upstream, also
  not something this package introduces.
- **It has no built-in voice.** NeuTTS clones from ~3 s of reference audio plus
  its exact transcript, so `ref_audio` and `ref_text` are required
  configuration. A NeuTTS provider without them is skipped at build with that
  reason, rather than failing the first time the agent speaks.

**What was and was not verified.** The adapter is exercised against a stand-in
model covering both backbones (PyTorch non-streaming and GGUF streaming), both
audio formats, every error path, and — the part most likely to be wrong — that a
synchronous, CPU-bound forward pass does not block the event loop:

```text
RESULT torch backbone -> 24kHz              48000B = 1.000s  streaming=False
RESULT gguf backbone -> streaming           48000B = 1.000s  streaming=True
RESULT gguf streaming -> 8kHz mulaw          8000B = 1.000s  streaming=True
RESULT event loop stayed responsive       7 ticks during a 0.4s blocking infer
```

Without the worker thread that tick count would be zero and every other call on
the process would stall for the length of the utterance.

**The real weights were never downloaded** — the repositories are gated and no
HF token was available here. So the plumbing is verified and the model is not.

### Running it despite the numpy conflict

Two honest options, neither of which is "add it to `pyproject.toml`":

**A separate virtualenv, accepting the pin break.** `uv pip install` does not
re-resolve the project, so it will install `neutts` and upgrade numpy past
Rasa's ceiling. Rasa continued to import and run in that state here, but it is
an unsupported combination and nothing guarantees the next release tolerates it:

```bash
uv pip install 'neutts>=1.4.1' 'torchao==0.14.0'   # breaks the numpy pin
```

**A sidecar, which is the version worth building.** Run NeuTTS in its own
process with its own dependency tree and talk to it over localhost. The
dependency conflict then never has to be resolved at all, the model stays warm
across restarts of the agent, and a crash in a research-grade stack cannot take
the call with it. That is a small HTTP service plus a thin adapter, and it is
the shape this should take before anyone runs it in production.

## Format conversion

Vendors return what they like: OpenAI raw 24 kHz PCM, Speechmatics a 16 kHz WAV,
ElevenLabs raw PCM at whatever `output_format` asked for. Rasa wants 24 kHz or
48 kHz linear, or 8 kHz mu-law for telephony. `voicerouter/audio.py` is the one
place that converts, and it is streaming-aware for two reasons that only show up
on a real call:

- **HTTP chunks split PCM frames.** A chunk ending mid-sample makes `audioop`
  refuse outright — this is a crash, and it was found by running telephony
  format against a live vendor rather than by reading.
- **The resampler carries state.** `audioop.ratecv` returns a state that must be
  fed back in. Dropping it does not raise; it adds a click at every chunk
  boundary, several times a second.

Verified deterministically: 1.000 s in, 1.000 s out at all three target formats,
fed in 1023-byte chunks so frames split on nearly every boundary.

## What it gives you

**Silence stops being a failure mode.** When a provider fails before its first
byte, the next one speaks the sentence — across vendors, including ones Rasa does
not ship. Two genuinely broken built-ins, then two third-party adapters:

```text
RESULT served_by='openai' bytes=156000
HEALTH rime(broken)       open     fail=1 ok=0
HEALTH deepgram(broken)   open     fail=1 ok=0
HEALTH openai             closed   fail=0 ok=2
HEALTH speechmatics       closed   fail=0 ok=0
```

The first failure is the real Rime `lang=None` misconfiguration (HTTP 400), the
second a Deepgram model that does not exist. The caller hears OpenAI.

**Configure more vendors than you have keys for.** A provider whose credentials
are absent is skipped with a log line, not an exception — so one
`integrations.yml` covers laptop, CI and production, and each runs on whatever
it has:

```text
[info] voicerouter.asr.provider_skipped  provider=azure  reason='credentials not configured'
[info] voicerouter.asr.ready             providers=['speechmatics']  skipped=['azure']
```

`make probe` reports this before a call rather than during one.

**It routes on what the failure meant, not just that one happened.** This is
the difference between a router and a wrapper. Every failure is classified, and
the class decides how long — if ever — that provider is skipped:

| Failure | Class | Consequence |
|---|---|---|
| `401` / `403`, rejected key | `auth` | **disabled** — no amount of waiting fixes a wrong key |
| `400` / `422`, malformed request | `config` | **disabled** — the config is wrong, not the vendor |
| `402`, "insufficient credit", quota text | `quota` | parked ~15 min; the account has to be topped up |
| `429` | `rate_limit` | reopens after the vendor's own `Retry-After`, else ~20 s |
| `5xx`, timeout, connection reset | `transient` / `unavailable` | ~15–30 s |

The signals come from real exception types — `aiohttp`, `websockets`,
`botocore`, `google-api-core` — plus the message text, because a wrapped
exception loses the attributes but usually keeps the number. AWS gets special
handling: it sends `ThrottlingException` with a **400**, which a status-only
reading would file as permanently broken.

Seen end to end, with the genuine Rime misconfiguration as the primary:

```text
[warning] voicerouter.tts.connect_failed provider=rime(misconfigured)
          verdict='config (HTTP 400) — skipping permanently'
TURN 1: served_by='deepgram'
TURN 2: served_by='deepgram'          # rime is not retried at all
HEALTH  rime(misconfigured)  disabled  kind=config
```

Turn 2 is the point. A wrapper would spend an attempt on Rime every sentence for
the length of the call; the router already knows the answer.

**The voice only changes when it has to.** Switching provider means the caller
hears a different person start speaking, so that is reserved for failures where
the current provider genuinely cannot serve — credits gone, key rejected, API
unreachable, config broken. A rate limit or a 503 is a *not right now*, so the
router retries the same provider first and the voice stays put:

```text
[info] voicerouter.tts.retrying_same_provider provider=rime
       verdict='rate_limit (HTTP 429) — skipping for 2s'
       note='keeping the caller's voice'
```

With one exception, because the rule has a limit: if the vendor's own
`Retry-After` is longer than a second, a different voice *sooner* beats the
right voice late. A vendor saying "come back in seven seconds" is telling you to
route around it, not to leave the caller in silence.

**Health outlives the call.** Rasa builds ASR and TTS engines per call —
`_get_asr_and_tts_engines` runs inside *"run streaming tasks and teardown for
one call"* — so a registry owned by the engine is discarded at every hangup and
the next caller rediscovers the same dead vendor. At any real call volume that
is the failover cost paid on the first utterance of every conversation, forever.
The registry is process-scoped by default:

```text
call 1: served_by='deepgram'   rime=disabled     # discovered here
call 2: served_by='deepgram'   rime=disabled     # not retried
call 3: served_by='deepgram'   rime=disabled     # not retried
```

Set `policy.health_scope: call` to opt out. A shared store across workers is the
obvious next step and is not built.

**Two deliberate asymmetries.** A provider merely *cooling down* stays on the
candidate list at lower priority, because a vendor rate-limited ten seconds ago
still beats silence. A provider *disabled* is dropped entirely, because it fails
identically every time — trying it buys no chance of audio and delays the
provider that might. And a later success never clears `disabled`: a rejected key
is not fixed by a request that cannot happen.

When nothing is left, the error says which providers are out and why —
`no TTS provider available — rime: disabled (config); deepgram: quota, retry in
870s` — rather than just that none remain.

**A dead vendor is tried once, not every sentence.** Each failure opens a
circuit for a cooldown window; the attempt after that is a probe, and one
success closes it. Unhealthy providers stay on the list at lower priority,
because a provider in cooldown is still better than silence.

## Routing on evidence, and per utterance

Configured order is a configuration decision, not a routing one. Two policies
turn it into a measured one.

**`selection: latency`** orders healthy providers by rolling p95
time-to-first-audio — the number that decides whether an agent feels alive, and
one Rasa already instruments. A provider needs at least three samples before it
is trusted, so one lucky call cannot reorder the chain.

There is a real limit worth stating: the router only measures providers it
actually uses, so with everything healthy it never learns that provider #2 was
faster. `policy.explore_rate` (default **0**) occasionally tries the runner-up
to keep its measurement fresh. It is off by default because exploring spends a
real caller's turn on a possibly-worse voice — turn it up if you would rather
pay a little quality to find out.

**`policy.utterance_classes`** routes on what is being said. An agent's
"one moment" and its "transferring four hundred pounds to Sam Rivera, shall I go
ahead?" are not worth the same voice, and nothing in Rasa can express that — a
channel has one TTS engine.

```yaml
policy:
  utterance_classes:
    filler:
      max_chars: 32
      patterns: ["^(ok|okay|got it|one moment|sure)\\b"]
      prefer: [neutts-local, deepgram]
```

```text
"One moment."                                        -> deepgram-cheap
"Transferring four hundred pounds to Sam Rivera…"    -> rime-premium
```

Preference is a **reordering, never a restriction**: if the cheap voice is down
the caller still hears the filler in the expensive one rather than hearing
nothing. Classification is deliberately dumb — length and optional patterns —
because an LLM call to decide how to say a three-word acknowledgement would cost
more than the synthesis it is economising on.

## Observability

`health_snapshot()` and `metrics_snapshot()` expose per-provider state,
attempts, failures by class and p95 latency. The same data emits as
OpenTelemetry counters and histograms — `voicerouter.tts.success`,
`.failure` (tagged with the failure class), `.failover`, `.first_audio` —
through whatever exporter the deployment already configures in `endpoints.yml`.
When tracing is not set up the instruments are no-ops, so nothing has to branch
and telemetry can never break a call.

## Which vendor is best on your audio?

The question every voice team has, and the one a vendor's own benchmark page
cannot answer, because it was not measured on your callers.

```bash
make bench
```

It replays a committed fixture corpus through every ASR adapter this machine can
actually reach, and reports what it measured:

```
Latency per utterance (ms)
  adapter              n      min   median      p95      max
  vosk-local           6       48      120      212      212
  whisper-local        6      102      108      112      112

Inter-vendor agreement (1.00 = identical after normalisation)
                     vosk-local whisper-lo
  vosk-local               1.00       0.79
  whisper-local            0.79       1.00

Disagreement hotspots (worst first — the audio worth listening to)
  digits              0.40  ████████
  transfer            0.62  ████████████
  reference           0.71  ██████████████
  balance             1.00  ████████████████████
```

**Agreement is the signal, because the engine gives you nothing else.** Rasa's
`NewTranscript` carries exactly one field, `text` — there is no confidence score
to read, by design. So the only quality evidence obtainable without forking
rasa-pro is whether independent vendors heard the same thing. Where they
diverge is where a caller is about to be misunderstood, which is why the
hotspot list names fixtures rather than scores: it tells you which audio to go
and listen to. Above, the digit string is the worst — which is exactly where
real ASR vendors disagree, and why account numbers are worth a confirmation
step.

### It never costs anything by default

The default run needs no credentials, contacts no paid vendor, and does not
fail when one is unconfigured. Every unreachable adapter is skipped **and
reported as skipped**, with the vendor's own reason:

```
  skip  deepgram         no DEEPGRAM_API_KEY — not configured here
  skip  speechmatics     no SPEECHMATICS_API_KEY — not configured here
  run   vosk-local       ......
  run   whisper-local    ......
  skip  azure            no AZURE_SPEECH_API_KEY — not configured here
```

A configured cloud vendor is skipped too — reachable is not the same as free.
Benchmarking one is opt-in and says so:

```bash
make bench BENCH_ARGS=--include-cloud    # makes billable calls
```

Reachability is not decided twice: `make bench` calls the same `probe()` that
backs `make probe`, so the benchmark and the diagnostic cannot disagree about
what this machine can reach.

To get a credential-free comparison you need two local adapters:

```bash
uv sync --prerelease=allow --extra local-asr   # vosk + faster-whisper
# Vosk also needs a model; unpack one from https://alphacephei.com/vosk/models
# into models/ and bench will find it.
```

With neither installed every adapter skips, the run still exits clean, and it
says there was nothing to compare — which is the honest outcome on a bare CI
runner, not a failure.

### The corpus, and why WER is sometimes absent

`tests/fixtures/audio/` holds six short banking utterances, about half a
megabyte in total. They are synthesised by `scripts/make_fixtures.py` from the
host's own TTS: no third-party audio to license, and — more importantly — no
recorded caller audio, which is exactly what a public repository must never
contain.

Because the generator knows the text it synthesised, each clip ships with a
genuine reference transcript, so a word error rate is legitimate here:

```
Word error rate (against the corpus reference transcripts)
  vosk-local          5.45%
  whisper-local      23.46%
```

Point the corpus at your own recordings and you will usually have no reference.
Then **the WER column is omitted entirely** — not zeroed, not left blank, not
filled with a plausible number. Agreement needs no ground truth, so an
unlabelled corpus of real caller audio still produces the signal you came for.

Those two percentages are a fact about six synthetic sentences and this
machine. They are not a claim about either vendor.

## Tests

```bash
make test      # 73 tests, no network, no credentials, no models
```

They cover the decisions rather than the vendors: how each failure is
classified, whether a voice may change, who is tried next, and that audio
conversion preserves duration across split frames. Those are what has to keep
working when someone else edits this, and they are exactly what live vendor
testing cannot pin down.

`tests/test_bench.py` covers the benchmark's arithmetic on the same terms —
agreement, latency, and the rule that a word error rate is never reported
without a reference transcript to measure against.

## What it does not do

Stated plainly, because these are the cases where a router could mislead you.

- **It cannot rescue a sentence already being spoken.** If a provider dies
  mid-stream those bytes are on the wire; failing over would replay the first
  half in a second voice. The sentence is truncated, the provider is marked
  unhealthy, and the *next* sentence comes from someone else.
- **It cannot recover audio the caller already spoke.** When an ASR stream dies,
  audio sent during the failure is gone — speech is not replayable, and buffering
  every call's raw audio to pretend otherwise is a worse trade. The router
  reconnects and resumes, and logs that a gap occurred.
- **It does not normalise vendor dialects.** `rime` wants `voice` plus an
  ISO-639-3 `language`; `deepgram` wants `model`; ElevenLabs wants a voice *id*;
  OpenAI needs `model_id` rather than `model`, because `TTSEngineConfig` keeps a
  deprecated top-level `model` and rejects a config carrying both. Each provider
  entry is that vendor's own config. A shared vocabulary is a later stage.
- **NeuTTS is an optional install, on purpose.** It pulls torch, torchaudio and
  transformers — multiple gigabytes that everyone else using the router should
  not pay for. `uv pip install 'neutts>=1.4.1' 'torchao==0.14.0'` opts in, and
  the provider is skipped with a clear reason until you do.
- **`audioop` is deprecated and gone in Python 3.13.** Rasa's own audio handling
  uses it too, so this is a shared constraint rather than one this package adds
  — but the conversion layer will need replacing before 3.13.
- **It does not route by cost, latency or content** yet. Order is the policy:
  first healthy provider wins.
- **The benchmark does not rank vendors.** `make bench` measures agreement and
  latency *on the corpus you give it*. Six synthetic utterances cannot tell you
  which vendor is best on your callers; point it at your own audio for that.

## Layout

| Path | What |
|---|---|
| `voicerouter/routed_tts.py` | `RoutedTTS` — failover before first byte |
| `voicerouter/routed_asr.py` | `RoutedASR` — reconnect-and-resume on stream death |
| `voicerouter/base.py` | provider specs, policy, and building engines through Rasa's factories |
| `voicerouter/health.py` | per-provider circuit breaker |
| `voicerouter/contract.py` | asserts the router still covers what Rasa calls |
| `voicerouter/providers/` | adapters for OpenAI, ElevenLabs, Speechmatics, AssemblyAI |
| `voicerouter/audio.py` | streaming format conversion shared by every HTTP adapter |
| `examples/` | one copy-pasteable config block per vendor |
| `voicerouter/bench.py` | agreement, latency and WER arithmetic for the benchmark |
| `scripts/probe_providers.py` | which vendors this machine can reach |
| `scripts/bench_asr.py` | replays the fixture corpus through every reachable ASR |
| `scripts/make_fixtures.py` | regenerates the synthetic corpus (macOS, rarely needed) |
| `tests/fixtures/audio/` | six synthetic utterances with reference transcripts |

## The contract check

The router is deliberately **not** a `TTSEngine` / `ASREngine` subclass. Rasa
never type-checks engines, and the base classes carry per-connection state that
would have to be kept in step with whichever child is active. Satisfying the
surface Rasa actually calls is simpler and less fragile.

The risk in that trade is a future Rasa release calling something new and the
router raising `AttributeError` mid-call. So the surface is **derived from the
installed Rasa** rather than written down:

```bash
make contract
#   RoutedTTS: 8/8 of the surface Rasa calls
#   RoutedASR: 8/8 of the surface Rasa calls
#   contract holds against the installed rasa-pro
```

It runs in `make verify`, needs no credentials and no network, and fails at
startup rather than at 3am.

## Quick start

```bash
make install
make env        # fill in RASA_LICENSE and OPENAI_API_KEY; voice keys optional
make verify     # contract + which vendors you can reach
make train
make inspect
```

Only `RASA_LICENSE` and `OPENAI_API_KEY` are needed to train — every voice key is
optional, and the router runs on whichever you have.

The agent here is deliberately tiny — one persona, two skills — because its job
is to exercise the router, not to be a product.

## In a real agent

[`examples/mantle-voice-routed-skills`](../../examples/mantle-voice-routed-skills)
is the worked example: a full banking agent whose ASR and TTS are both routed.
It is the same Vela as
[`mantle-voice-rime-skills`](../../examples/mantle-voice-rime-skills) (one
vendor Rasa ships) and
[`mantle-voice-speechmatics-skills`](../../examples/mantle-voice-speechmatics-skills)
(one it does not), so the three can be read side by side with the voice stack as
the only variable.

It also carries two things this pattern does not:

- **`make drill`** — replays a banking call with a vendor failing on a schedule
  and prints who speaks each line and why, so the failover rule can be seen
  without running a vendor out of credits.
- **`stacks/`** — four complete alternative configurations of the same agent
  (resilient, cost-tiered, hyperscaler, offline) with the trade-off each one
  makes written down, switchable with `make stack STACK=<name>`.

## Verified

- `validate_project` and `rasa train` pass on the catalog pin
- TTS failover exercised against **live** Rime and Deepgram, with a genuinely
  broken primary
- ASR routing exercised against **live** Deepgram and Speechmatics, including a
  provider skipped for missing credentials
- The contract check passes against the installed `rasa-pro`
- `make bench` exercised end to end with **two local ASR adapters** (Vosk
  0.3.44 and faster-whisper `tiny.en`) transcribing all six fixtures, and with
  every adapter skipped on a machine with no credentials and no local models

Not verified: telephony channels end to end (browser Inspector only), and no
vendor beyond the four above — `azure` and `cartesia` are configured but were
skipped for want of keys.

## Where this is going

Stage 1 of [`docs/VOICE_ROUTER.md`](../../docs/VOICE_ROUTER.md), which sets out
the rest: per-utterance routing, first-audio racing, shadow ASR evaluation, a
normalised voice vocabulary, and local-first with cloud burst. It is meant to
graduate into its own repository once those land.

## Licence

Apache 2.0 — see the repository root [LICENSE](../../LICENSE). Rasa Pro is a
commercial framework under its own terms.
