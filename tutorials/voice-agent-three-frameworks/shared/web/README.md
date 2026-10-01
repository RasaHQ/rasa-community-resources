# shared/web: one voice page for all three agents

A static page ([`index.html`](index.html), [`app.js`](app.js),
[`pcm-worklet.js`](pcm-worklet.js)) that calls the Cedar Clinic agent from a
browser: microphone in, agent speech out, a transcript, and the protocol's
own numbers (handshake rate, markers acknowledged, the latency on the last
end marker). It speaks Rasa's browser_audio protocol, documented in
[`PROTOCOL.md`](PROTOCOL.md), so the same page works against the Rasa,
LangGraph and Strands servers.

```bash
make -C rasa run                              # the Rasa version on :5005 (or start another version)
python3 shared/web/serve.py rasa              # page on http://127.0.0.1:8765/, relaying to :5005
python3 shared/web/serve.py langgraph --agent http://127.0.0.1:5006
```

Open http://127.0.0.1:8765/, press **Call**, allow the microphone and say
"I'm Maria Alvarez, born March fourteenth, nineteen sixty-eight. I need a
refill of my lisinopril." You can also type a caller turn.

## Why a relay

A browser cannot set a header on a WebSocket, and the conversation id is the
`X-Rasa-Sender-Id` header ([PROTOCOL 1](PROTOCOL.md#1-connection)).
[`serve.py`](serve.py) (standard library) serves the page, and for
`/relay?sender=<id>` opens its own WebSocket to the agent with that header
and copies bytes both ways untouched. Knowing the id, it can also read the
conversation's events (`/api/events`) for the transcript.

Opened any other way (or with `?ws=ws://host:port/...`), the page connects
straight to the WebSocket URL in the box. Audio still works both ways; the
transcript shows only what you typed, since the wire carries no text.

## What the page does

- **Microphone:** `getUserMedia` with echo cancellation, an AudioWorklet that
  resamples to the handshake rate and posts 20 ms frames of 16-bit PCM, each
  sent as `{"audio": base64}`. By default the microphone sends silence while
  the agent is speaking, so speakers without headphones do not feed the
  agent its own voice (barge-in is off in all three versions anyway).
- **Playback:** each `{"audio"}` chunk is scheduled back to back on a Web
  Audio context at the handshake rate.
- **Markers:** acknowledged once the audio before them has played, or when the
  next audio starts if they arrived on an empty queue (PROTOCOL 3).
- **`interruptPlayback`:** stops playback and drops queued audio and markers.
- **Typed input:** `{"text": ...}`.

`window.cedarVoice` exposes the page's state for debugging and for the
headless check.
