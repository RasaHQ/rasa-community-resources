# Vela — voice banking on a custom Speechmatics ASR engine

```text
Author:        Rod Rivera
Assessed on:   2026-08-26
Assessed by:   Rod Rivera
Verified with: rasa-pro 3.20.0.dev1, Python 3.11+, uv
Audience:      Practitioners whose ASR provider is not one Rasa ships
Time:          45–60 minutes
```

The same banking agent as [`mantle-voice-rime-skills`](../mantle-voice-rime-skills),
with one thing changed: the **listening half** runs on Speechmatics, which Rasa
does not ship an engine for.

That is the whole point. Rasa has built-in ASR engines for Deepgram and Azure.
When your provider is neither, you are not stuck bolting an orchestrator on
outside Rasa — you write an engine and give Rasa its dotted path.

## How a custom engine is wired

```yaml
# integrations.yml
channels:
  inspector:
    asr:
      name: engines.speechmatics.SpeechmaticsASR   # dotted path, not a built-in name
      language_map: { en: { language: en } }
      operating_point: enhanced
      max_delay: 1.0
      enable_partials: true
    tts:
      name: deepgram                                # built-in, so this half is one line
```

Rasa looks `name` up in its built-in registry, misses, and falls back to
`class_from_module_path` — then calls `from_config_dict` on whatever it finds.
The class is marked as a beta feature on load, which is a log line, not a
restriction.

The engine is [`engines/speechmatics.py`](engines/speechmatics.py), about 200
lines including the reasoning. The four methods that matter:

| Method | What it has to do |
|---|---|
| `open_websocket_connection` | Connect **and** send `StartRecognition` — Speechmatics transcribes nothing until it arrives |
| `rasa_audio_bytes_to_engine_bytes` | Pass raw audio through, counting messages for `last_seq_no` |
| `signal_audio_done` | Send `EndOfStream` with that count |
| `engine_event_to_asr_event` | Map `AddPartialTranscript` → `UserIsSpeaking`, `AddTranscript` → `NewTranscript` |

## Three things the docs will not tell you

All three were found by running the thing, not by reading.

**Configuration is not in the query string.** Deepgram's engine encodes its
settings into the websocket URL. Speechmatics does not: the socket opens
unconfigured and the first message must be `StartRecognition`. Sending audio
first gets you a connection that never transcribes anything, with no error.

**`current_language_config` is not the map entry you wrote.** It is a
`CurrentLanguageConfig`, whose engine-side field is `engine_language_key`, with
`rasa_language_key` as the fallback. There is no `.language`. Reading one raises
`AttributeError` on the **first connection attempt** — long after config load,
in the middle of a call.

**`max_delay` fragments transcripts.** At `1.0` seconds, one spoken sentence
came back as four finals:

```text
['Please block', 'my card', 'ending', '4532.']
```

Rasa's turn-taking reassembles these, but if you are logging or testing against
raw finals, expect fragments and not sentences. Raise `max_delay` for whole
utterances at the cost of latency.

## What it covers

Identical to the Rime resource: `check_balance`, `transfer_money`,
`report_lost_card`, `transaction_history`, plus session start, intro and
goodbye. Keeping the agent the same is deliberate — the voice stack is the only
variable between the two resources.

## Quick start

```bash
make install
make env          # creates .env from .env.example — then fill in the four keys
make verify
make train
make inspect
```

## Required secrets

| Variable | Purpose |
|---|---|
| `RASA_LICENSE` | Rasa Pro Developer Edition licence |
| `OPENAI_API_KEY` | LLM for routing and conversation |
| `SPEECHMATICS_API_KEY` | Speech-to-text — [portal.speechmatics.com](https://portal.speechmatics.com/) |
| `DEEPGRAM_API_KEY` | Text-to-speech (Aura) |

`SPEECHMATICS_API_KEY` is needed to **run**, not to build: `rasa train`
completes with it entirely unset, because the engine is only constructed when a
call starts. Checked rather than assumed, which is why this resource is not
declared in `[tool.rasa-catalog] required-secrets` — CI trains it in full.

## Verification

The engine was exercised against the live Speechmatics API through Rasa's own
`asr_engine_from_config`, so the path under test is the one the channel uses —
not a hand-rolled client:

```text
resolved engine : engines.speechmatics.SpeechmaticsASR
test audio      : 135418 bytes  (spoken by Rime, so the input is real speech)
UserIsSpeaking  : 6
NewTranscript   : ['Please block', 'my card', 'ending', '4532.']
```

Worth noting what came back: the sentence spoken was *"…ending four five three
two"*, and Speechmatics returned **`4532`**. Spoken digit strings arrive as
numerals, which is exactly what `normalise_digits` in
[`lib/bank.py`](lib/bank.py) assumes — the assumption is now measured rather
than hoped for.

## What breaks

- **Beta extension point.** Custom engines log a beta-feature warning on load.
  The interface is stable enough to build on, but it is not covered by the same
  compatibility promise as a built-in.
- **One region, hardcoded default.** `endpoint` defaults to the EU realtime
  endpoint (`wss://eu.rt.speechmatics.com/v2`). Override it in `integrations.yml`
  for another region.
- **Partials during silence are dropped.** Speechmatics emits empty partials
  between utterances; forwarding them would read as the caller speaking, so the
  engine filters them. If you need voice-activity signalling, that is the place
  to add it.
- Balances live in memory — see the [Rime resource](../mantle-voice-rime-skills)
  for the same caveat.

## Where it came from

Migrated from the `feature/speechmaticsRefactoring` branch of
[`RasaHQ/rasa-rime-voice-demo`](https://github.com/RasaHQ/rasa-rime-voice-demo),
where Speechmatics was reached through a standalone `services/` layer driving
Rasa over REST, alongside a scripted caller/manager scenario harness.

The harness is not carried over. What it demonstrated — that Speechmatics can
drive a Rasa conversation — is better shown as an engine Rasa loads itself,
because that version works with the Inspector, with real telephony channels, and
with Rasa's own turn-taking rather than beside it.

## Licence

Apache 2.0 — see the repository root [LICENSE](../../LICENSE). Rasa Pro is a
commercial framework under its own terms.
