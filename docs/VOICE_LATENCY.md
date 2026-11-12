# Measuring voice response latency

The user-facing interval is **end of user speech to the first audible bot
sample**. The target is less than 1,500 ms for typical turns. A completed LLM
turn, an ASR configuration value, a tool dispatch or the first network audio
chunk does not establish that interval.

This maintainer tool uses Python's standard library. It does not load Rasa, a
licence, keys, models, a microphone or a provider. Analysis is offline. Only
`capture` executes the command explicitly supplied by its caller; use it only
in an already authorized environment. It does not create a Codespace or change
its secrets. Keep the ordinary example command and its mock/vendor boundary.

## Record an already authorized Codespaces run

From the example's terminal, this wraps the same `make run` command:

```sh
python ../../scripts/voice_latency.py capture --output "$HOME/voice-latency/events.jsonl" --timeout 600 -- make run
```

The runtime's usual console output remains visible. The private timing file
retains only recognized markers and numeric metadata, with run-local session
labels. It does not retain console text, transcripts, URLs, environment values
or command arguments. The ordinary console may still contain private runtime
output: do not publish it or include secrets in screenshots. Recording never
authorizes a new model/speech call; retain failed and interrupted attempts and
do not rerun them automatically.

Press Ctrl+C to stop the wrapper. It stops its owned process group, including
descendants, and keeps partial timing observations. Exit 124 means timeout;
130 means interruption; 126 means cleanup could not be verified (including a
permission refusal). No alternate signal method or retry follows a refusal.
Otherwise the runtime's exit code is returned. Existing capture files are
never overwritten. The artifact includes the observed child exit/cleanup state.

Analyse a timing file from the repository root:

```sh
python scripts/voice_latency.py analyse "$HOME/voice-latency/events.jsonl" --format events --output "$HOME/voice-latency/report.json"
```

An existing SDK console log can also be analysed offline:

```sh
python scripts/voice_latency.py analyse /path/to/retained-sdk.log --format sdk-log --output /path/to/new-report.json
```

The SDK log adapter reports actual `mantle.turn.started` to
`mantle.turn.completed` spans and iteration counts, voice-session context when
explicitly logged, dispatch counts, ASR settings and cold model-loading to
voice-initialization markers. Cancellation stays visible and is excluded from
successful latency percentiles. A truncated subsequent turn cannot inherit an
earlier turn's start. Second-resolution timestamps produce explicit uncertainty
intervals; they cannot demonstrate a subsecond improvement.

`first_runtime_log_to_worker_ready` starts at the first timestamp in the log,
not at clicking the Codespaces button or executing the command. Capture's
separate monotonic span ends when its wrapper observes a `Worker ready` line;
stdout buffering can delay that observation. Model-loading to voice-channel
initialization can include download and other initialization work, not just the
model transfer. Neither is a warm per-turn response measurement.

## Full per-turn boundary contract

The normalized JSONL format accepts these timing boundaries from a receiving
instrumentation adapter. Each record has `schema` =
`rasa.voice-latency-event/v1`, `event`, a run-local `session`, a `turn`, a `clock`,
nonnegative `at_ms` and `resolution_ms`. No arbitrary payload fields survive
validation. The tool does not authenticate caller-supplied observations.

| Component | Required boundaries | Clock requirement |
| --- | --- | --- |
| User-perceived response | `speech.end` → `audio.first_played` | Same browser/audio clock; final user speech sample to first actually rendered audible bot sample |
| ASR finalization | `speech.end` → `asr.final` | Same clock or an independently qualified adapter that supplies a common clock |
| Orchestration | `turn.started` → `turn.completed` | Same server clock; optional integer `iterations` |
| Each MCP call | `mcp.started` → `mcp.completed` | Same server clock and unique `call` identity per invocation |
| TTS first chunk | `tts.requested` → `tts.first_chunk` | Same clock; a returned network chunk is not audible output |

Use a new clock identity after a browser reload, clock reset or process change.
Do not subtract browser and server wall clocks without a qualified clock join.
Do not replace audible output with WebSocket receipt or playback scheduling.
Current ordinary SDK INFO logs do not supply all these boundaries; absent
markers remain `missing_boundary` with null durations. Completing a browser,
ASR or TTS adapter is required before claiming end-to-end voice improvement.

The existing `scripts/case_builds/voice_driver.py` assigns its
`first_audible` timestamp when a received PCM chunk contains sound, before its
emulated speaker drains the queue. That is a non-silent **receive** observation,
not browser playback. Do not rename that field to `audio.first_played` when
adapting old case-build results. A receiving browser adapter must observe the
first non-silent sample consumed by the playback worklet and retain any output
latency/calibration limits; queued or scheduled audio alone is insufficient.

Reports retain incomplete calls, ambiguous duplicate boundaries, reversed times
and cancellations. P50 is the median and P95 the nearest-rank 95th percentile;
the actual non-cancelled sample count is always reported. Streaming phases can
overlap, so their durations are never added to manufacture end-to-end latency.
No sample distribution or provenance is invented and no target pass is implied
by an empty result. Use the same frozen scenario, runtime/version, model, region
and clock method for baseline and successor, disclose changed settings, and
report cold separately from warm runs.

## Change one cause at a time

- Prefetch a cold barge-in model into the **same cache the runtime uses**, during
  Codespace build rather than the first voice session. Pin and check the actual
  model revision/files, then compare genuinely cold and warm starts. A cached
  path alone does not prove the first session is download-free.
- Compare supported ASR endpointing/utterance-end settings with actual speech
  boundaries. A lower configured delay is not its measured latency saving.
- Use the observed iteration counts to identify orchestration round trips.
  Preserve consent, identity, confirmation and refusal controls when reducing
  iterations; a faster unsafe conversation is not an improvement.
- Compare model/region choices only with explicit runtime/cost authority and
  unchanged scenarios. Source inspection and scripted timing controls are not
  provider or microphone measurements.
