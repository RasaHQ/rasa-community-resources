# The browser_audio protocol, as all three servers speak it

The voice page ([`index.html`](index.html), [`app.js`](app.js)) and the spec
runner ([`../spec/run_spec.py`](../spec/run_spec.py), through
[`scripts/case_builds/voice_driver.py`](../../../../scripts/case_builds/voice_driver.py))
talk to every version of the agent the same way: Rasa's `browser_audio`
WebSocket channel. The Rasa version gets it from the runtime. The LangGraph
and Strands versions must implement the server side of what follows, so the
same page and the same runner work against all three.

This describes rasa-pro 3.21.0.dev5
(`rasa/core/channels/voice_stream/browser_audio.py` and `voice_channel.py`
in the wheel), as observed by the companion's voice driver in the case-build
runs and in this tutorial's Rasa run.

## 1. Connection

- **Path:** `ws://<host>:<port>/webhooks/browser_audio/websocket`. Use this
  path in every version, so only the port differs.
- **Conversation id:** if the upgrade request carries an `X-Rasa-Sender-Id`
  header whose value matches `^[A-Za-z0-9._:-]{1,128}$`, that value is the
  conversation id. Otherwise the server makes one up (Rasa: `inspect-<uuid>`).
  The spec runner always sends the header, and the clinic's audit log, the
  events endpoint and the LLM meter join on that id, so a server must pass it
  unchanged to `cedar_clinic.tools` as the `conversation_id`. It is for
  trusted local transports only: any client can claim any id.
- **Language:** an optional `?language=<code>` query parameter. The Cedar
  Clinic agent is English only and ignores it.
- **Subprotocols and extensions:** none. The server must not require
  `Sec-WebSocket-Protocol`, and nothing is compressed.

A browser cannot set a header on a WebSocket, which is why
[`serve.py`](serve.py) relays the page's socket and adds `X-Rasa-Sender-Id`.

## 2. Frames

Every frame after the upgrade is a JSON text frame.

**Server to client, first:**

```json
{"type": "handshake", "sample_rate": 24000}
```

The rate applies to audio in both directions. All three versions use 24000
(16-bit linear PCM); Rasa also allows 8000 (mu-law on the wire, decoded as
L16), 16000 and 48000. The client sends nothing but may buffer until it has
the handshake.

**Client to server:**

| Frame | Meaning |
|---|---|
| `{"audio": "<base64>"}` | 16-bit little-endian mono PCM at the handshake rate. Clients send 20 ms frames continuously, silence included, like a microphone (480 samples, 960 bytes at 24 kHz) |
| `{"text": "<utterance>"}` | A caller turn as text: skips speech-to-text, still goes through the agent and text-to-speech. Empty text is ignored |
| `{"marker": "<id>"}` | Playback acknowledgement: the audio sent before marker `<id>` has finished playing |

Anything else is ignored.

**Server to client:**

| Frame | Meaning |
|---|---|
| `{"audio": "<base64>"}` | Agent speech, same encoding. Any chunk size |
| `{"marker": "<hex id>"}` | A playback marker (see 3) |
| `{"marker": "<hex id>", "latency": {...}}` | A marker carrying the latency of the current bot message (see 4) |
| `{"interruptPlayback": true}` | Stop playing and drop queued audio (barge-in). Only sent when interruptions are on; they are off in all three versions |

There is **no end-of-turn frame and no text of what anyone said**. The
wire carries audio and markers only. The page shows a transcript by reading
the conversation's events (section 5), and the runner knows a bot turn has
ended from the same events.

## 3. Markers

For each bot message the server sends, in order:

1. a marker before the first audio chunk (start),
2. the audio, with a marker after each full second of it (intermediate),
3. a marker after the last chunk (end), carrying `latency`.

Markers are ids the client must echo back as `{"marker": id}` once the audio
queued before the marker has played, in order. Rasa feeds the acknowledgements
to its playback tracking and silence handling
(`rasa/core/voice/event_composition/handlers/playback_tracking_handler.py`
and `silence_handler.py`), so it knows what the caller has actually heard. The rule both clients implement, from the legacy Inspector client:

- a marker that arrives while audio is queued is acknowledged when the audio
  queued before it has finished playing;
- a marker that arrives on an empty queue is acknowledged when the next audio
  starts playing, not at once.

A server may use the acknowledgements or ignore them, but must accept them.

## 4. Latency on end markers

Rasa attaches this object to markers, and the voice page and the spec
runner read it from the first end marker after the caller stopped speaking:

```json
{"rasa_processing_latency_ms": 1560.5, "tts_first_byte_latency_ms": 900.4, "tts_complete_latency_ms": 1302.1}
```

| Field | Rasa's definition, which the other servers must follow |
|---|---|
| `rasa_processing_latency_ms` | From the moment the final transcript of the caller's turn (or a `{"text"}` frame) arrived to the moment the turn's first bot message was ready to be spoken. Only the first bot message of a turn has it |
| `tts_first_byte_latency_ms` | From starting text-to-speech for this message to its first audio byte |
| `tts_complete_latency_ms` | From starting text-to-speech for this message to its last audio byte |

Rasa omits `latency` when any of the three is unknown, and repeats the
previous message's figures on markers sent during pacing silence; the
runner keeps only changed objects. Servers other than Rasa: send all three on
the end marker of every bot message, computed as above.

## 5. The events endpoint (not part of browser_audio)

The runner and the page's transcript need to see the conversation.

- **Rasa:** `GET /conversations/<id>/tracker` (with `--enable-api`), the
  tracker. Its `user`, `bot` and `bot_turn_ended` events are used.
- **LangGraph and Strands:** `GET /conversations/<id>/events`, returning the
  same shape:

```json
{"events": [
  {"event": "bot", "text": "Cedar Clinic prescription line. ...", "timestamp": 1790807166.2},
  {"event": "bot_turn_ended", "timestamp": 1790807166.3},
  {"event": "user", "text": "Hi, this is Maria Alvarez, ...", "timestamp": 1790807171.9},
  {"event": "bot", "text": "Okay, I'll pull up your record now.", "timestamp": 1790807173.6},
  {"event": "bot", "text": "I can send a request about ...", "timestamp": 1790807178.0},
  {"event": "bot_turn_ended", "timestamp": 1790807178.1}
]}
```

Rules the runner relies on (`voice_driver.turn_done_in_tracker`):

- one `user` event per caller turn the agent answered, appended when the
  final transcript arrives (its `timestamp`, in epoch seconds, is how the
  runner measures end of speech to transcript);
- one `bot` event per message the agent speaks;
- one `bot_turn_ended` after the last bot message of each turn, including the
  greeting. A caller turn is over when every new `user` event has its own
  `bot_turn_ended` and the audio has drained;
- a caller turn that the speech-to-text splits in two gets two `user` events
  and must be answered twice (Rasa does this); a server that merges them
  instead must still end with a `bot_turn_ended` for each `user` event it
  logged.

Return 404 or an empty `events` list for an unknown id. Also serve
`GET /health` (200 when ready); the runner waits on it (Rasa: `/status`).

## 6. Hangup

The client closes the socket. Rasa then runs one more agent turn on
`/session_end` that nobody hears; the runner waits for it so its model calls
stay with the right conversation. Other servers need not do anything, and
the runner waits until the events stop changing.

## 7. What a server has to write

For the comparison, everything in this file that a server implements is
**voice loop** code (see [`../../README.md`](../../README.md)):
the WebSocket endpoint, the handshake, decoding and encoding audio frames,
feeding the speech-to-text and acting on end of utterance, sentence
chunking for text-to-speech, sending audio with markers and latency, the
events endpoint, and whatever it does about barge-in, silence and fillers.
The Speechmatics clients themselves are the **voice adapter**
([`../speech/`](../speech/)).
