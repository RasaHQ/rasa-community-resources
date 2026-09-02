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

**A dead vendor is tried once, not every sentence.** Each failure opens a
circuit for a cooldown window; the attempt after that is a probe, and one
success closes it. Unhealthy providers stay on the list at lower priority,
because a provider in cooldown is still better than silence.

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
- **`audioop` is deprecated and gone in Python 3.13.** Rasa's own audio handling
  uses it too, so this is a shared constraint rather than one this package adds
  — but the conversion layer will need replacing before 3.13.
- **It does not route by cost, latency or content** yet. Order is the policy:
  first healthy provider wins.

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
| `scripts/probe_providers.py` | which vendors this machine can reach |

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

## Verified

- `validate_project` and `rasa train` pass on the catalog pin
- TTS failover exercised against **live** Rime and Deepgram, with a genuinely
  broken primary
- ASR routing exercised against **live** Deepgram and Speechmatics, including a
  provider skipped for missing credentials
- The contract check passes against the installed `rasa-pro`

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
