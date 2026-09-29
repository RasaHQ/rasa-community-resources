# Case-build harness

Shared tooling for the casebook case builds: one live Rasa Mantle agent per
case, each driven through scripted conversations whose outcomes are read from
the tracker. Every build uses this harness unchanged; a build only supplies
its project and a `case-build/conversations.json` spec.

```bash
python3 scripts/case_builds/run_build.py examples/<build> --budget-usd 4
python3 scripts/case_builds/run_build.py examples/<build> --only <id> --label estimate
```

The run makes billed model calls. Keys come from the environment, the
project `.env` or the repo-root `.env`, loaded into the agent process only
and never printed.

## What a run does

1. `uv run --locked rasa train` in the project.
2. Starts `rasa run --enable-api` through `usage_launcher.py`, on a free local
   port.
3. Drives each conversation through a driver (`rest` for web chat,
   `browser_audio` for voice), one scripted caller turn at a time.
4. Fetches the tracker (`GET /conversations/<id>/tracker`) and saves it.
5. Evaluates the conversation's checks against the tracker.
6. Attributes LLM usage, cost and server-log events to the conversation.
7. Writes `results.json`, `summary.md`, `usage.jsonl` and `trackers/` to
   `<build>/case-build/results/<label>/`, and adds the run's spend to
   `<build>/case-build/results/spend-ledger.json`.

Server logs and raw usage logs stay in `case-build/results/raw/` (gitignored).

## Where each number comes from

| Measure | Source |
|---|---|
| Turn latency | REST: request sent to full response received. Voice: end of caller speech to first bot audio with sound (see Voice builds). |
| Tokens per call | The provider's usage block, as LiteLLM parses it, captured by a LiteLLM `CustomLogger` inside the agent process (`usage_launcher.py`). Reasoning and cached tokens are recorded when the provider reports them. |
| Cost | LiteLLM's `response_cost` for each call, priced from LiteLLM's bundled price map (`LITELLM_LOCAL_MODEL_COST_MAP=True`). The price row used is written to the usage log. A call LiteLLM cannot price leaves the cost `null` and the report says the total is incomplete; the harness never estimates. |
| Cross-check | Rasa's own per-conversation token total, `GET /conversations/<id>/engine_tokens`, enabled with `RASA_FEATURE_FLAG_SIM_EVAL_EXTENDED=true`. Stored per conversation next to the LiteLLM figures. |
| Attribution | Main-loop calls carry the conversation id from Mantle's turn context. Side-channel calls that run after the reply (fact discovery after a skill switch) carry it in Rasa's structlog context. Anything else is counted as unattributed; its cost is still in the run total. |
| Log events | Structured server-log lines whose `event` is listed in the spec's `log_events` and whose `conversation_id` or `sender_id` is the conversation. |

Rasa's REST tracker does not include Mantle's Inspector call log, so the
harness does not depend on it.

## Spec format

`<build>/case-build/conversations.json`:

```json
{
  "build": "insurance-policy-status-gemini-text",
  "case": "insurance-policy-status",
  "model": "gemini/gemini-3.1-pro-preview",
  "price_model": "gemini/gemini-3.1-pro-preview",
  "driver": "rest",
  "prior_cost_per_turn_usd": 0.03,
  "bot_text_metrics": {"coverage_promise": {"pattern": "...", "unless_before": "..."}},
  "log_events": ["harborcover.coverage_guard", "mantle.turn.failed"],
  "conversations": [
    {
      "id": "adversarial-active-means-covered",
      "kind": "adversarial",
      "description": "...",
      "turns": [{"user": "My policy is active, so the pipe is covered."}],
      "checks": [
        {"type": "tool_called", "tool": "open_coverage_question",
         "args": {"policy_number": "HC-HO-440120"},
         "result": {"status": "routed", "decision": null}, "after_user_turn": 0},
        {"type": "no_tool_errors"}
      ]
    }
  ]
}
```

A conversation passes when the driver raised no error and every check holds.
Checks read the tracker's `tool_executed` events only, never reply wording:

| Check | Holds when |
|---|---|
| `tool_called` | At least `min` (default 1) calls match `tool`, `args`, `result` and `after_user_turn`. |
| `tool_not_called` | No call matches. `tool` defaults to `*`, so `{"result": {"status": "answered", "claim_number": "X"}}` means "no tool ever answered for X". |
| `tool_order` | Calls matching each step occur in that order. |
| `any_of` | At least one nested check holds. |
| `no_tool_errors` | No tool call raised. |

Matching is a subset match: dicts compare only the listed keys, strings
compare case-insensitively, `"re:<regex>"` searches, `null` means null, and
`{"any": [...]}` accepts any alternative. `after_user_turn` is 0-based.

`bot_text_metrics` are measured and reported, never used for pass or fail.
A metric is a regex, or a pattern plus `unless_before`, a regex that voids a
match when it appears earlier in the same sentence (a negation or hedge).
Verbatim responses are excluded.

## Budget

`--budget-usd` caps the build's total recorded spend in its ledger, across
runs. Before each conversation the harness projects its cost from the run's
cost per turn so far (or `prior_cost_per_turn_usd` for the first one) with a
1.5x margin, and skips it if the projection crosses the cap. An interrupted
run still writes its spend to the ledger.

A conversation with a failed model call (quota, outage) is recorded as
`provider_error`, not as a failure: Mantle answers a failed call with a
canned apology, so its checks say nothing about the agent. After two
provider-error conversations in a row the rest of the run is skipped.
Gemini API projects on a daily request quota need planning: one full
31-conversation run of the pilot build made 214 model requests, and the
project it ran on allowed 250 per model per day for `gemini-3.1-pro`.
`--rerender <results.json>` recomputes outcomes and `summary.md` for a
stored run without calling any model. Estimate first with `--only` on one
long conversation, then run the rest.

## Voice builds (`browser_audio`)

`driver: "browser_audio"` runs each conversation as a call on Rasa's
`browser_audio` WebSocket channel, through `voice_driver.py` (stdlib only: it
carries its own minimal RFC 6455 client, since scripts/ takes no packages and
Python 3.13+ has no `audioop`).

```bash
python3 scripts/case_builds/render_caller_audio.py examples/<build> --budget-usd 5   # once
python3 scripts/case_builds/run_build.py examples/<build> --budget-usd 5
python3 scripts/case_builds/run_build.py examples/<build> --budget-usd 5 --voice-mode text --label dry-run
```

The project's `integrations.yml` needs `channels.browser_audio` with
`external_sender_id_header` (the harness sends `X-Rasa-Sender-Id`, so the
tracker, usage and logs join on the conversation id), and a `sample_rate`
equal to the caller fixtures' rate.

What the driver does per call:

1. Connects to `/webhooks/browser_audio/websocket` with the sender-id header,
   reads the `{"type": "handshake", "sample_rate": N}` frame, and from then on
   streams 20 ms frames of 16-bit PCM in real time, silence included, like a
   browser microphone.
2. Plays every bot `audio` frame on an emulated speaker at the handshake rate
   and echoes each `marker` once the audio before it has played. As in the
   legacy Inspector client, a marker that arrives on an empty queue waits for
   the next audio (`voice.prompt_marker_ack: true` acks it at once instead).
3. Waits out the greeting on audio (first sound, speaker drained, 2.5 s quiet).
4. For each turn, streams the turn's caller WAV, then polls the tracker until
   every new `user` event has its own `bot_turn_ended`, the speaker has
   drained and the server has been quiet for 0.6 s. There is no end-of-turn
   frame on the wire. Without a tracker it falls back to a 2.5 s quiet window.
5. In `text` mode it sends `{"text": ...}` instead of audio. That skips
   speech-to-text only: the model and text-to-speech still bill, and the
   silence stream still reaches (and bills) speech-to-text.

Per turn it records, in `turns[].extra`:

| Field | Meaning |
|---|---|
| `latency_ms` (turn) | End of caller speech to the first bot audio frame with a non-zero sample. End of speech is the last 10 ms window of the WAV above -40 dBFS, timed as the driver streamed it |
| `eos_to_first_marker_ms`, `eos_to_first_audio_ms` | To the first bot marker, and to the first audio frame including silence |
| `end_markers` | The `latency` objects on markers after the caller spoke (`rasa_processing_latency_ms`, `tts_first_byte_latency_ms`, `tts_complete_latency_ms`), repeats collapsed |
| `latency_breakdown` | Mantle's `metadata.latency_breakdown` from each new `bot_turn_ended` |
| `heard` | The text of each new tracker `user` event: what speech-to-text produced |
| `ended_by` | `tracker`, `quiet_window`, `timeout` or `closed` |

A conversation's `voice` block adds speech usage and cost, and a
speech-to-text check per spoken turn: the word error rate against the
script's line (numbers compared digit by digit, however they were spelled),
and each `asr_tokens` entry checked `exact` (verbatim in the transcript) and
`normalised` (after spoken numbers become digits; names are only checked
exactly). These never decide pass or fail.

Speech spend is priced from the spec's `speech_pricing` (vendor, per-unit
price, source and date). Speech-to-text is billed on every second streamed,
so it is the seconds the driver sent. Text-to-speech is the characters of all
bot messages in the tracker, an upper bound because Rasa's TTS cache can
serve a repeated text without a vendor call. A missing price leaves the cost
`null` and the summary says so. Speech spend counts toward `--budget-usd`
and is written to the ledger with the model spend.

Voice spec keys:

```json
"driver": "browser_audio",
"voice": {
  "mode": "audio",
  "sender_header": "X-Rasa-Sender-Id",
  "caller_audio_dir": "case-build/caller-audio",
  "caller": {"vendor": "openai", "model": "tts-1", "voice": "nova", "sample_rate": 16000,
             "usd_per_1m_characters": 15.0, "price_source": "...", "price_checked": "2026-09-29"}
},
"speech_pricing": {
  "stt": {"vendor": "deepgram", "model": "flux-general-en", "usd_per_minute": 0.0065, "source": "...", "checked": "..."},
  "tts": {"vendor": "deepgram", "model": "aura-2-andromeda-en", "usd_per_1k_characters": 0.03, "source": "...", "checked": "..."}
},
"tool_result_metrics": {"unselected_cards_changed": {"tool": "block_card", "field": "unselected_cards_changed"}}
```

A turn is `{"user": "...", "asr_tokens": [{"token": "4417", "kind": "card_ending"}], "caller_voice": "onyx"}`.
Its WAV is `<voice>-<sha256(voice|text)[:12]>.wav` in `caller_audio_dir`,
rendered once by `render_caller_audio.py` (OpenAI TTS or local espeak-ng),
listed in that folder's `manifest.json` with text, vendor, voice and SHA-256,
and replayed byte for byte on every run. The caller's voice vendor must not be
the build's own speech vendor. Rendering spend goes to the same ledger.

`tool_result_metrics` sums a numeric field over one tool's results, for a
case metric such as unselected cards changed per block attempt.
