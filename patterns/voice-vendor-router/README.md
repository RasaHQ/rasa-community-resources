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

## What it gives you

**Silence stops being a failure mode.** When a provider fails before its first
byte, the next one speaks the sentence. Verified against live vendors, using the
real Rime misconfiguration that returns HTTP 400:

```text
[warning] voicerouter.tts.connect_failed  provider=rime-misconfigured  error=…status 400
[info]    voicerouter.tts.connected       provider=deepgram
          served by 'deepgram', 117120 bytes
          rime-misconfigured   open     fail=1 ok=0
          deepgram             closed   fail=0 ok=2
```

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
- **It does not normalise vendor dialects.** `rime` still wants `voice` plus an
  ISO-639-3 `language`; `deepgram` wants `model`. Each provider entry is that
  vendor's own config. A shared vocabulary is a later stage.
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
| `engines/speechmatics.py` | a vendor Rasa does not ship, included to prove the point |
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
