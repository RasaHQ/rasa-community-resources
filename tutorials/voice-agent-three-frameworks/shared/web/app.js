// One browser voice client for all three agents. It speaks Rasa's
// browser_audio WebSocket protocol (see PROTOCOL.md):
//
//   server -> {"type": "handshake", "sample_rate": N}      first frame
//   client -> {"audio": base64 16-bit LE mono PCM at N Hz} 20 ms frames
//   client -> {"text": "..."}                               typed input, skips speech-to-text
//   server -> {"audio": ...} | {"marker": id, "latency"?} | {"interruptPlayback": true}
//   client -> {"marker": id}                                once the audio before it has played
//
// Served by serve.py, the page connects through its relay, which adds the
// X-Rasa-Sender-Id header a browser cannot set, and reads the conversation's
// events for the transcript. Opened from any other static host it connects
// straight to the WebSocket URL you give it; audio works, and the transcript
// shows only what you typed.

"use strict";

const S = {
  ws: null,
  rate: 0,
  ctx: null,
  mic: null,
  worklet: null,
  nextTime: 0,
  sources: [],
  pending: [], // markers: {id, ackAt} (ackAt null = wait for the next audio)
  handshake: null,
  relay: false,
  config: null,
  sender: null,
  framesSent: 0,
  audioChunksIn: 0,
  audioSecondsIn: 0,
  markersIn: 0,
  markersAcked: 0,
  interrupts: 0,
  lastLatency: null,
  events: [],
  typed: [],
  halfDuplex: true,
  closedReason: null,
};
window.cedarVoice = S; // for the headless check and for debugging

const $ = (id) => document.getElementById(id);

function log(text) {
  const line = document.createElement("div");
  line.textContent = `${new Date().toLocaleTimeString()}  ${text}`;
  $("log").prepend(line);
}

function b64FromBuffer(buffer) {
  const bytes = new Uint8Array(buffer);
  let s = "";
  for (let i = 0; i < bytes.length; i += 0x8000) s += String.fromCharCode.apply(null, bytes.subarray(i, i + 0x8000));
  return btoa(s);
}

function floatsFromB64(data) {
  const raw = atob(data);
  const view = new DataView(new ArrayBuffer(raw.length));
  for (let i = 0; i < raw.length; i++) view.setUint8(i, raw.charCodeAt(i));
  const out = new Float32Array(raw.length >> 1);
  for (let i = 0; i < out.length; i++) out[i] = view.getInt16(i * 2, true) / 32768;
  return out;
}

function send(obj) {
  if (S.ws && S.ws.readyState === WebSocket.OPEN) S.ws.send(JSON.stringify(obj));
}

// ---------------------------------------------------------------- playback

function playing() {
  return S.ctx && S.nextTime > S.ctx.currentTime + 0.005;
}

function onAudio(data) {
  const samples = floatsFromB64(data);
  if (!samples.length) return;
  const buffer = S.ctx.createBuffer(1, samples.length, S.rate);
  buffer.copyToChannel(samples, 0);
  const source = S.ctx.createBufferSource();
  source.buffer = buffer;
  source.connect(S.ctx.destination);
  const start = Math.max(S.nextTime, S.ctx.currentTime + 0.03);
  source.start(start);
  source.onended = () => (S.sources = S.sources.filter((s) => s !== source));
  S.sources.push(source);
  S.nextTime = start + buffer.duration;
  S.audioChunksIn += 1;
  S.audioSecondsIn += buffer.duration;
  // A marker that arrived on an empty queue is acknowledged once this audio
  // starts to play, as the legacy Inspector client does.
  for (const m of S.pending) if (m.ackAt === null) m.ackAt = start + 0.01;
}

function onMarker(msg) {
  S.markersIn += 1;
  if (msg.latency) S.lastLatency = msg.latency;
  S.pending.push({ id: msg.marker, ackAt: playing() ? S.nextTime : null });
  renderStats();
}

function onInterrupt() {
  S.interrupts += 1;
  for (const source of S.sources) {
    try {
      source.stop();
    } catch (_) {}
  }
  S.sources = [];
  S.pending = [];
  S.nextTime = S.ctx ? S.ctx.currentTime : 0;
}

function tick() {
  if (!S.ctx) return;
  const now = S.ctx.currentTime;
  while (S.pending.length && S.pending[0].ackAt !== null && now >= S.pending[0].ackAt) {
    send({ marker: S.pending.shift().id });
    S.markersAcked += 1;
  }
  if (S.worklet) S.worklet.port.postMessage({ muted: S.halfDuplex && playing() });
  $("speaking").textContent = playing() ? "agent speaking" : "";
}

// ---------------------------------------------------------------- microphone

async function startMic() {
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    log("no microphone API here; text only");
    return;
  }
  try {
    S.mic = await navigator.mediaDevices.getUserMedia({
      audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true, autoGainControl: true },
    });
  } catch (err) {
    log(`microphone not available (${err.name}); text only`);
    return;
  }
  await S.ctx.audioWorklet.addModule("pcm-worklet.js");
  const source = S.ctx.createMediaStreamSource(S.mic);
  S.worklet = new AudioWorkletNode(S.ctx, "pcm-capture", { processorOptions: { targetRate: S.rate } });
  S.worklet.port.onmessage = (e) => {
    send({ audio: b64FromBuffer(e.data.pcm) });
    S.framesSent += 1;
    $("level").value = Math.min(1, e.data.level * 3);
  };
  source.connect(S.worklet);
  // The worklet must be pulled by the graph; route it to a silent sink.
  const sink = S.ctx.createGain();
  sink.gain.value = 0;
  S.worklet.connect(sink).connect(S.ctx.destination);
  log(`microphone on, resampled ${S.ctx.sampleRate} Hz -> ${S.rate} Hz, 20 ms frames`);
}

// ---------------------------------------------------------------- transcript

function renderTranscript() {
  const box = $("transcript");
  box.textContent = "";
  const rows = S.relay
    ? S.events.filter((e) => e.event === "user" || e.event === "bot")
    : S.typed.map((t) => ({ event: "user", text: t }));
  for (const e of rows) {
    const div = document.createElement("div");
    div.className = e.event;
    div.innerHTML = `<b>${e.event === "user" ? "Caller" : "Agent"}</b> `;
    div.append(document.createTextNode(e.text || ""));
    box.append(div);
  }
  box.scrollTop = box.scrollHeight;
}

async function pollEvents() {
  if (!S.relay || !S.sender) return;
  try {
    const r = await fetch(`/api/events?sender=${encodeURIComponent(S.sender)}`);
    if (r.ok) {
      const doc = await r.json();
      S.events = doc.events || [];
      renderTranscript();
    }
  } catch (_) {}
}

function renderStats() {
  const l = S.lastLatency || {};
  $("stats").textContent =
    `handshake ${S.rate || "-"} Hz | mic frames sent ${S.framesSent} | audio in ${S.audioSecondsIn.toFixed(1)} s ` +
    `(${S.audioChunksIn} chunks) | markers ${S.markersAcked}/${S.markersIn} acked | ` +
    `last end marker: processing ${fmt(l.rasa_processing_latency_ms)} ms, TTS first byte ${fmt(l.tts_first_byte_latency_ms)} ms`;
}

const fmt = (v) => (typeof v === "number" ? Math.round(v) : "-");

// ---------------------------------------------------------------- connection

function newSender() {
  const rand = crypto.getRandomValues(new Uint32Array(2));
  return `web-${Date.now().toString(36)}-${rand[0].toString(36)}${rand[1].toString(36)}`;
}

async function connect() {
  if (S.ws) return;
  S.ctx = new AudioContext();
  await S.ctx.resume();
  S.sender = newSender();
  const url = S.relay
    ? `${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/relay?sender=${S.sender}`
    : $("wsurl").value.trim();
  log(`connecting to ${url}`);
  const ws = new WebSocket(url);
  S.ws = ws;
  ws.onmessage = async (event) => {
    let msg;
    try {
      msg = JSON.parse(event.data);
    } catch (_) {
      return;
    }
    if (!S.handshake) {
      if (msg.type !== "handshake") {
        log(`expected a handshake frame, got ${event.data.slice(0, 80)}`);
        return;
      }
      S.handshake = msg;
      S.rate = msg.sample_rate;
      log(`handshake: ${S.rate} Hz` + (S.relay ? `, conversation ${S.sender}` : ""));
      $("state").textContent = "connected";
      renderStats();
      if ($("usemic").checked) await startMic();
      return;
    }
    if ("audio" in msg) onAudio(msg.audio);
    else if ("marker" in msg) onMarker(msg);
    else if (msg.interruptPlayback) onInterrupt();
    renderStats();
  };
  ws.onclose = (e) => {
    S.closedReason = `closed (${e.code})`;
    log(`connection ${S.closedReason}`);
    hangup(false);
  };
  ws.onerror = () => log("websocket error");
}

function hangup(close = true) {
  if (close && S.ws) S.ws.close(1000);
  S.ws = null;
  if (S.mic) S.mic.getTracks().forEach((t) => t.stop());
  S.mic = null;
  S.worklet = null;
  onInterrupt();
  S.handshake = null;
  $("state").textContent = "not connected";
}

function sendText() {
  const text = $("text").value.trim();
  if (!text || !S.handshake) return;
  send({ text });
  S.typed.push(text);
  $("text").value = "";
  renderTranscript();
}

async function init() {
  try {
    const r = await fetch("/api/config");
    if (r.ok) {
      S.config = await r.json();
      S.relay = !!S.config.relay;
    }
  } catch (_) {}
  const params = new URLSearchParams(location.search);
  if (params.get("ws")) {
    S.relay = false;
    $("wsurl").value = params.get("ws");
  }
  $("mode").textContent = S.relay
    ? `through serve.py's relay to ${S.config.agent} (${S.config.framework})`
    : "direct WebSocket (no bot transcript: a browser cannot send the conversation-id header)";
  $("wsurl").disabled = S.relay;
  $("connect").onclick = connect;
  $("hangup").onclick = () => hangup(true);
  $("send").onclick = sendText;
  $("text").onkeydown = (e) => e.key === "Enter" && sendText();
  $("halfduplex").onchange = (e) => (S.halfDuplex = e.target.checked);
  setInterval(tick, 20);
  setInterval(pollEvents, 500);
  renderStats();
}

init();
