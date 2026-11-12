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

The runtime's usual console output remains visible through deadline-aware,
nonblocking forwarding with at most one read chunk pending. An open pipe that
is not being consumed cannot bypass the capture timeout or owned-group cleanup. The private timing file
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

Capture also accepts validated normalized event JSON emitted by a native
adapter on the runtime console, with or without a logging prefix. SDK console
projection handles plain, ANSI-coloured and prefixed JSON event logs. Arbitrary
transcript text containing an event name does not create a timing event.

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
and cancellations. Multiple completions make a turn terminally ambiguous; all
cancellation/failure flags survive in either order and the turn is excluded from
successful percentiles. A valid audio-only observation needs no completion event. P50 is the median and P95 the nearest-rank 95th percentile;
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

## Prefetch the pinned SDK 3.21.0.dev5 barge-in model

Run inside the example's locked environment, as the same user and with the same
Hugging Face cache settings used by its runtime:

```sh
uv run --locked python ../../scripts/prefetch_voice_model.py --download
uv run --locked python ../../scripts/prefetch_voice_model.py
```

The first command explicitly permits downloading the three public model files.
The second checks only the existing cache and never permits network fetches.
Neither command contacts a speech/LLM provider, reads a licence, opens a voice
session or loads ONNX inference. Downloads remain in the ordinary runtime cache;
no cache directory or SDK environment is copied between hosts.

The helper checks the installed SDK version, resolved `main` snapshot revision,
byte lengths and SHA-256 digests of tokenizer, config and quantized ONNX files.
It uses the same `main` lookup as the inspected SDK loader so that a separate
revision-only cache does not falsely pass. An SDK/revision/hash mismatch fails
without a warm-cache claim. It does not update those pins automatically. This
command does not support the newer SDK's different CDN downloader. Do not add
it to a generic image shared by projects with other SDK versions.

To move first-session download work into setup, run the explicit download command
after the resource's locked install, then keep the same cache through launch.
Compare fresh-process SDK model loading with that verified cache, including an
`HF_HUB_OFFLINE=1` control. Record preparation cost separately: prefetch shifts
work earlier rather than removing it from total setup. This isolates model load,
not browser response latency, and should be measured again on each target.

## Browser receiving adapter for a bounded fictional caller

The optional `scripts/voice_latency_browser/` probe sends an **existing fictional
mono WAV**, then measures from its last sample above −40 dBFS to the first bot
sample above −40 dBFS consumed by its AudioWorklet. Both boundaries use the same
AudioContext sample clock. It does not use the microphone or generate caller
audio. Its JSONL contains only event labels, run-local identities and times.

In an already authorized example Codespace, start the ordinary trained agent's
`browser_audio` server. In a second terminal, from the repository root:

```sh
python3 -m http.server 8765 --bind 127.0.0.1 --directory scripts/voice_latency_browser
```

Open the local page in the same browser host as the local WebSocket endpoint
(default `ws://127.0.0.1:5005/webhooks/browser_audio/websocket`). A remote
maintainer browser needs its separately authorized forwarded WebSocket address;
use the GitHub port access controls, never embed credentials in the URL. The
example must already expose the standard browser_audio protocol. The page does
not set provider keys, configure a vendor or change the server's access controls.

Click **Connect once**; this starts the live speech session and can bill the
configured providers. Wait for the greeting to finish, choose an existing
fictional WAV under 30 seconds, then click **Send one fixture**. Click **Stop**
after the response. Use **Save run report** to preserve partial events, failure
state, the measurement method and the pre-close audio sample rate/base/output
latency. Save this report even when no usable pair was produced. It contains no
endpoint, filename, transcript, audio or credentials. **Save timing JSONL** remains
available for the analyser's `events` format above. The page refuses pending/overlapping turns, caps its queue and stops after
180 seconds; it never reconnects or retries. Reloading and reconnecting is a new
explicit run. Stopping the page closes the socket; stop the agent separately.

This is **synthetic fixture to rendered browser audio**, not human VAD or an
acoustic speaker measurement. The page reports the browser's base/output latency
separately; it does not silently add it or call a headless dummy audio device a
physical speaker. It does not by itself provide the server-side ASR/MCP/TTS
boundaries or prove a typical latency target. Preserve these limits with every
report, retain failed/no-pair attempts, and use the same caller fixture and clock
method for a successor. Protocol controls are in
`node scripts/voice_latency_browser/test-clock-worklet.cjs`; they make no speech
or model call. A headless browser receiving control is separate from live speech
qualification.

The run report keeps the observed browser output latency separate from the event
interval; it never silently adds device latency or fills missing measurements
with zero. Stop is idempotent, and connecting after Stop requires an explicit
page reload. The exported report remains available after stopping. Offline page
controller and artifact controls run with `node
scripts/voice_latency_browser/test-probe.cjs` and
`node scripts/voice_latency_browser/test-artifact.cjs`.

## Snapshot SDK phase metadata before stopping the agent

After the response, while the same authorized SDK server is still alive, use
its observed conversation identity from the private runtime console locally:

```sh
python3 scripts/voice_tracker.py --base-url http://127.0.0.1:5005 --conversation-id OBSERVED_ID --output "$HOME/voice-latency/server-phases.json"
```

Run this in the Codespace, then stop the browser probe and the agent. The tool
makes one read-only request to the explicit loopback HTTP API, with a total
three-second deadline (including a slow-drip response), a response-size limit
and no redirects, proxies, credentials or retries. It refuses existing output
files before requesting anything. A failed collection produces a private
`not_collected` artifact containing the error type; no response body or identity
is written. It never opens a speech or model session.

The projection retains only allowlisted numeric SDK `BotTurnEnded` metadata:
LLM first-token/generation, TTS first-byte/generation and prediction-loop times
when present. Missing values remain null; invalid values are identified. SDK
`user_perceived_latency_ms` is explicitly labelled
`server_trigger_to_first_output_ms`; it is **not** the browser speech/playback
interval. Server ordinals do not establish a browser clock or turn join.
ASR-final and per-MCP invocation timing remain separate native-adapter events;
they are not manufactured from this snapshot. Never disable API authentication
to use this limited local collector: a protected endpoint should retain its
existing authorized adapter/event route.
