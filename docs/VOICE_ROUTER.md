# A voice router for Mantle — recon and design

    Status:        Recon. Nothing built yet.
    Author:        Rod Rivera
    Written:       2026-09-02
    Investigated:  `3.20.0.dev6`, installed and read
    Question:      What would an "OpenRouter for voice vendors" give Mantle
                   that Mantle does not already have?

**The finding in one line:** Mantle's LLM is a routed group with five routing
strategies and provider fallback. Mantle's voice stack is a hardcoded
singleton, and when a vendor fails the caller hears silence.

Everything below is read out of the installed package, with file and line
references, so it can be re-checked when the version moves.

---

## 1. What the voice stack is today

| | Today |
|---|---|
| Built-in ASR | `azure`, `deepgram` — `BUILT_IN_ASR_ENGINES` |
| Built-in TTS | `azure`, `cartesia`, `deepgram`, `rime` — `BUILT_IN_TTS_ENGINES` |
| Third-party providers | one extension point: an unrecognised `name` is loaded as a dotted path via `class_from_module_path`, marked beta (`voice_channel.py:205`, `:249`) |
| Engines per call | exactly one each — `_get_asr_and_tts_engines() -> Tuple[ASREngine, TTSEngine]` (`voice_channel.py:1479`) |
| Where that lives | `VoiceInputChannel` (`voice_channel.py:1300`), inherited by **all nine** channels: Twilio, Vonage, Genesys, Audiocodes, Jambonz, SignalWire, Chirp, browser, websockets |
| Multi-language | `language_map` per engine, with mid-session reconnect (`set_language`, `_reconnect_with_lock`) |
| TTS caching | in-process `OrderedDict` LRU keyed on `(text, audio_format)` — `tts_cache.py` |
| Observability | genuinely good: spans, metrics, per-turn recorders, first-audio latency (`rasa/tracing/voice/`) |

Two things to hold onto: **the extension point is shared by every channel**, and
**reconnect-mid-session machinery already exists**. Those are the two footholds a
router needs, and both are already there.

## 2. The asymmetry

The LLM side got a router. The voice side did not.

| | LLM | ASR / TTS |
|---|---|---|
| Config shape | `llm: {model_group: …}` + `model_groups:` with N models | one engine, inline |
| Multiple providers per role | yes | **no** |
| Routing strategies | `cost-based-routing`, `usage-based-routing`, `latency-based-routing`, `least-busy`, `simple-shuffle` (`shared/constants.py:247-253`) | **none** |
| Provider fallback | yes, via the LiteLLM router | **none** — no `fallback`/`failover`/`retry` vocabulary anywhere under `voice_stream/` |
| Self-hosted / local | `self_hosted_llm_client`, and `huggingface_local` for embeddings | **none** |

The `.dev6` release made the LLM group mandatory — the inline form was removed
outright. Voice was left on the shape the LLM just outgrew.

## 3. What that costs, concretely

**A TTS failure makes the agent mute.** Not degrade — mute:

```python
except TTSError as e:
    logger.error("voice_channel.tts_synthesis_error", error=str(e))
    voice_tracing.get_current_synthesize_speech_recorder().record_error(e)
    # TODO: add message that works without tts, e.g. loading from disc
    audio_stream = self.chunk_audio(generate_silence(self.audio_format))
```

`voice_channel.py:611`. The `TODO` is upstream's, not mine. One vendor blip and
the caller sits in silence with no recovery path.

**An ASR failure makes the agent deaf, at warning level.**

```python
except Exception as e:
    logger.warning(f"Error while streaming ASR events: {e}")
```

`asr_engine.py:362`. The event stream ends. The call does not.

**Every vendor speaks its own dialect, and the mistakes are silent.** Two found
while building the examples in this catalog:

- Rime's language map needs `language` *and* `voice`, where `language` is
  ISO-639-3 (`eng`) and the key above it is Rasa's (`en`). Omit it and the
  engine builds a URL containing `lang=None`; Rime answers **HTTP 400** at the
  first spoken word. Nothing fails at config load.
- Speechmatics puts no configuration in the query string — the socket opens
  unconfigured and the first message must be `StartRecognition`. And
  `current_language_config` is not the map entry you wrote: the engine-side
  field is `engine_language_key`, so reading `.language` raises
  `AttributeError` on first connection.

Each vendor added means learning a new dialect, and each dialect has a trap that
only shows up on a live call.

## 4. The design: the router *is* an engine

The whole proposal rests on one observation.

> `ASREngine` and `TTSEngine` are interfaces. A router that implements them can
> also consume them. It satisfies the same contract it multiplexes.

```yaml
# integrations.yml — no core change, works today
channels:
  inspector:
    tts:
      name: voicerouter.RoutedTTS
      policy: first-audio-wins
      providers:
        - name: rime
          language_map: { en: { voice: cove, language: eng } }
        - name: deepgram
          language_map: { en: { model: aura-2-andromeda-en } }
        - name: voicerouter.local.PiperTTS      # never fails, never mute
```

Consequences worth stating plainly:

- **Zero changes to Rasa.** It rides the documented extension point, so it works
  on all nine channels on day one.
- **Nothing to fork, nothing to wait for.** It ships from this repository.
- **It is a strict superset.** A one-provider router behaves exactly like that
  provider today.
- **It graduates cleanly.** If Rasa later grows real voice model groups, the
  router's `providers:` list is the same shape, and the config migrates.

## 5. What this offers that does not exist anywhere

Failover is the floor, not the pitch. These are the ideas worth building it for.

**Silence becomes impossible.** A failover chain terminating in a local engine
or pre-rendered audio. "The agent went quiet" stops being a failure mode.

**Routing by what is being said.** Backchannels and fillers — *"one moment"*,
*"got it"* — go to the cheapest, fastest, most cacheable path. Disclosures,
confirmations and amounts go to the best voice available. Mantle has no notion
that utterances differ in value; this is per-utterance policy, and nothing else
in the stack can express it.

**First-audio racing.** Start two providers, serve whichever returns audio
first, cancel the loser. Time-to-first-audio is the number that decides whether
a voice agent feels alive — and Mantle already instruments it, so the win is
measurable the day it lands.

**Shadow evaluation on real traffic.** Send the same audio to a second ASR,
serve the primary, log the disagreement. This is the OpenRouter arena idea
applied to voice: vendor comparison on *your* calls and *your* accents, rather
than on a vendor's benchmark page.

**One voice vocabulary.** `voice: warm-female-en` resolving per vendor, so
switching providers is not a re-learning exercise. Rime's `speaker`, everyone
else's `voice`, and the ISO-639-3 trap all collapse into one normalised
catalogue.

**Local-first, cloud-burst.** Local ASR/TTS as the default path with cloud
escalation on low confidence. This is the one nobody can do today: the voice
stack has no local story at all, while the LLM side has had `self_hosted` and
`huggingface_local` for a while.

**A cache that survives a restart**, is shareable across workers, and can be
pre-warmed from the response catalogue at train time. Today's is a per-process
dict that empties on deploy.

## 6. Staging

| Stage | Scope | Ships as |
|---|---|---|
| 0 | This document, agreed | — |
| 1 | `RoutedTTS` + `RoutedASR` wrapping built-ins, failover + health, config schema | a resource in this repo |
| 2 | Two providers Rasa does not ship, one of them local | adds the vendor-gap argument |
| 3 | Per-utterance policy, first-audio racing, shadow ASR | the differentiated part |
| 4 | Normalised voice catalogue; persistent, pre-warmed cache | the polish that makes it a product |
| 5 | Extract to its own repository, publish to PyPI | graduation |

Stage 1 is small — it is mostly the two adapter classes and a health/circuit
policy. Stages 3 and 4 are where the ideas live, and neither is reachable inside
Rasa's current shape without a router in front.

## 7. What I would want decided before building

1. **Router scope.** TTS and ASR only, or does it eventually cover the LLM too?
   Keeping it voice-only is the nimble answer, and the LLM already has a router.
2. **Local engine to bet on first.** The local option is the strongest
   differentiator and the biggest dependency question — a local TTS is a model
   download and a licence to check, not just an adapter.
3. **Does the shadow-evaluation data go anywhere?** Logged as spans is nearly
   free given the existing tracing. A comparison report is a product.
4. **Naming and home**, since it graduates.

## Related

- [`MIGRATING.md`](MIGRATING.md) — the breaking changes on this release line
- [`../examples/mantle-voice-rime-skills`](../examples/mantle-voice-rime-skills) — built-in TTS provider
- [`../examples/mantle-voice-speechmatics-skills`](../examples/mantle-voice-speechmatics-skills) — the custom-engine extension point, already exercised
