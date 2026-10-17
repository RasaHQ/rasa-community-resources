import { LOCALES, type Lang } from '../i18n/dictionaries';

/**
 * WebAudio-based speech-to-text fallback for environments where the Web
 * Speech API is non-functional (macOS Safari). Captures the microphone
 * with getUserMedia, resamples to 16 kHz mono int16 PCM, and pushes each
 * VAD-framed chunk to the local Whisper bridge (ws://localhost:8765),
 * which answers with the transcription as plain text.
 */

const WS_URL = 'ws://localhost:8765';
const TARGET_RATE = 16000;
const SILENCE_MS = 700;    // end a chunk shortly after the user stops talking
const MAX_DURATION_MS = 15000;  // keep long sentences in one chunk (splits garble words)
const MIN_CHUNK_MS = 300;   // ignore chunks shorter than this
const VAD_THRESHOLD = 0.030; // RMS above this counts as speech (0.01 catches ambient noise -> 14s chunks of silence)
const TRIM_AMPLITUDE = 400;  // int16 level below which leading/trailing audio is trimmed
const BRIDGE_TIMEOUT_MS = 120000; // the Whisper bridge is CPU-bound (medium model); give it time

export interface WhisperSttHandlers {
  onTranscript: (text: string) => void;
  onEnd: () => void;
  onError?: (error: string) => void;
}

let ctx: AudioContext | null = null;
let source: MediaStreamAudioSourceNode | null = null;
let node: ScriptProcessorNode | null = null;
let stream: MediaStream | null = null;
let active = false;
let wired = false;
let paused = false;
let stopping = false;
let starting = false;
let generation = 0;
let pcm: number[] = [];
let silenceStart: number | null = null;
let chunkSpeech = false;
let chunkStart = 0;
let langRef = 'fr';
let handlersRef: WhisperSttHandlers | null = null;

export function isWhisperSTTSupported(): boolean {
  return (
    typeof window !== 'undefined' &&
    typeof WebSocket !== 'undefined' &&
    !!navigator.mediaDevices?.getUserMedia
  );
}

/*
 * Whisper transcribes silence poorly (it tends to invent words around it).
 * Trim leading/trailing quiet samples with a small margin for better accuracy.
 */
function trimSamples(samples: number[]): number[] {
  let start = 0;
  while (start < samples.length && Math.abs(samples[start]) < TRIM_AMPLITUDE) start++;
  let end = samples.length;
  while (end > start && Math.abs(samples[end - 1]) < TRIM_AMPLITUDE) end--;
  if (start >= end) return samples.slice(0, 0);
  const margin = Math.round(TARGET_RATE * 0.15);
  const from = Math.max(0, start - margin);
  const to = Math.min(samples.length, end + margin);
  return samples.slice(from, to);
}

function toInt16Bytes(samples: number[]): Uint8Array {
  const bytes = new Uint8Array(samples.length * 2);
  for (let i = 0; i < samples.length; i++) {
    const v = Math.max(-32768, Math.min(32767, Math.round(samples[i])));
    bytes[i * 2] = v & 0xff;
    bytes[i * 2 + 1] = (v >> 8) & 0xff;
  }
  return bytes;
}

function base64FromBytes(bytes: Uint8Array): string {
  let bin = '';
  const CHUNK = 0x8000;
  for (let i = 0; i < bytes.length; i += CHUNK) {
    bin += String.fromCharCode.apply(null, Array.from(bytes.subarray(i, i + CHUNK)));
  }
  return btoa(bin);
}

function transcribe(samples: number[], lang: string): Promise<string> {
  return new Promise((resolve, reject) => {
    let ws: WebSocket;
    const timeout = setTimeout(() => {
      try { ws?.close(); } catch { /* ignore */ }
      reject(new Error('bridge timeout'));
    }, BRIDGE_TIMEOUT_MS);

    try {
      ws = new WebSocket(WS_URL);
    } catch (e) {
      clearTimeout(timeout);
      reject(e);
      return;
    }

    ws.onopen = () => {
      ws.send(
        JSON.stringify({
          type: 'audio',
          audio: base64FromBytes(toInt16Bytes(samples)),
          // Ask Whisper to auto-detect the spoken language instead of forcing
          // the UI language. Forcing 'fr' mis-decodes English speech (and
          // vice-versa); auto-detection keeps the transcript faithful to what
          // the user actually said.
          language: 'auto',
          sampleRate: TARGET_RATE,
        }),
      );
    };

    ws.binaryType = 'arraybuffer';

    ws.onmessage = async (e: MessageEvent) => {
      try {
        // The bridge replies with a binary UTF-8 frame; decode it robustly.
        let raw: string;
        if (typeof e.data === 'string') {
          raw = e.data;
        } else if (e.data instanceof ArrayBuffer) {
          raw = new TextDecoder().decode(e.data);
        } else if (e.data instanceof Blob) {
          raw = await e.data.text();
        } else {
          raw = String(e.data);
        }
        const msg = JSON.parse(raw) as { type?: string; text?: string; message?: string };
        if (msg.type === 'text') {
          clearTimeout(timeout);
          ws.close();
          const text = (msg.text || '').trim();
          console.info(`[whisperSTT] transcription: "${text}"`);
          resolve(text);
        } else if (msg.type === 'error') {
          clearTimeout(timeout);
          try { ws.close(); } catch { /* ignore */ }
          console.warn('[whisperSTT] bridge error:', msg.message);
          reject(new Error(msg.message || 'bridge error'));
        }
      } catch {
        /* ignore malformed frames */
      }
    };

    ws.onerror = () => {
      clearTimeout(timeout);
      try { ws.close(); } catch { /* ignore */ }
      reject(new Error('bridge error'));
    };
  });
}

function rms(buf: Float32Array): number {
  let sum = 0;
  for (let i = 0; i < buf.length; i++) {
    const s = buf[i];
    sum += s * s;
  }
  return Math.sqrt(sum / buf.length);
}

function pushFloat32(buf: Float32Array, sampleRate: number) {
  if (!active) return;
  const ratio = sampleRate / TARGET_RATE;
  for (let i = 0; i < buf.length; i += ratio) {
    const v = buf[Math.floor(i)];
    pcm.push(Number.isFinite(v) ? v * 32767 : 0);
  }

  const now = Date.now();
  if (rms(buf) > VAD_THRESHOLD) {
    chunkSpeech = true;
    silenceStart = null;
  } else if (silenceStart === null) {
    silenceStart = now;
  }

  const enough = pcm.length / TARGET_RATE >= MIN_CHUNK_MS / 1000;
  const silenced = silenceStart !== null && now - silenceStart >= SILENCE_MS;
  const maxed = now - chunkStart >= MAX_DURATION_MS;
  if (enough && (silenced || maxed)) void finalize();
}

async function finalize() {
  if (!active || stopping) return;
  active = false;
  const gen = generation;

  const samples = pcm;
  pcm = [];
  silenceStart = null;

  // Buffer too short (e.g. the assistant's own voice): discard, keep listening.
  if (samples.length / TARGET_RATE < MIN_CHUNK_MS / 1000) {
    if (paused || gen !== generation) return;
    chunkSpeech = false;
    chunkStart = Date.now();
    active = true;
    return;
  }

  // No actual speech detected in this chunk → drop it (avoids Whisper
  // hallucinating French/English nonsense on noise or silence).
  if (!chunkSpeech) {
    console.info('[whisperSTT] chunk skipped (no speech)');
    if (paused || gen !== generation) return;
    chunkSpeech = false;
    chunkStart = Date.now();
    active = true;
    return;
  }
  chunkSpeech = false;
  console.info(`[whisperSTT] sending chunk (${(samples.length / TARGET_RATE).toFixed(1)}s)`);

  try {
    const trimmed = trimSamples(samples);
    const text = await transcribe(trimmed, langRef);
    if (gen === generation && !stopping && text && !paused) {
      handlersRef?.onTranscript(text);
    }
  } catch (err) {
    if (gen === generation && !stopping) handlersRef?.onError?.('bridge_unreachable');
  }

  if (stopping) {
    cleanup();
    handlersRef?.onEnd?.();
    handlersRef = null;
    return;
  }

  // A pause happened while transcribing → discard the result, stay silent.
  if (paused || gen !== generation) return;

  // Continuous listening: start a fresh chunk right away.
  chunkStart = Date.now();
  active = true;
}

function cleanup() {
  try { node?.disconnect(); } catch { /* ignore */ }
  try { source?.disconnect(); } catch { /* ignore */ }
  node = null;
  source = null;
  wired = false;
  stream?.getTracks().forEach((t) => t.stop());
  stream = null;
  active = false;
  starting = false;
}

function fullStop() {
  stopping = true;
  cleanup();
  handlersRef?.onEnd?.();
  handlersRef = null;
}

async function acquireAndRun() {
  if (starting || active) return;
  starting = true;
  try {
    // Create and wake the AudioContext synchronously, BEFORE the first await,
    // so creation stays inside the user gesture. On Safari a context created
    // after an await starts 'suspended' and resume() outside a gesture is
    // rejected — the ScriptProcessor fires nothing and the mic looks "on"
    // while capturing silence. Creating it up front keeps it 'running'.
    const Ctor: typeof AudioContext =
      window.AudioContext ||
      (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
    ctx = ctx ?? new Ctor();
    if (ctx.state === 'suspended') {
      try { await ctx.resume(); } catch { /* retried after wiring below */ }
    }
    if (stopping) {
      fullStop();
      return;
    }

    if (!stream) {
      stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true },
        video: false,
      });
    }
    if (stopping) {
      fullStop();
      return;
    }

    source = source ?? ctx.createMediaStreamSource(stream);
    node = node ?? ctx.createScriptProcessor(4096, 1, 1);
    const sampleRate = ctx.sampleRate;
    node.onaudioprocess = (e) => pushFloat32(e.inputBuffer.getChannelData(0), sampleRate);

    // Always wire the graph; "paused" only controls whether capture flows.
    if (!wired) {
      node.connect(ctx.destination);
      source.connect(node);
      wired = true;
    }

    // Last-resort wake: if the context is still suspended (e.g. the browser
    // deferred it), ask again once the graph is live; if it refuses, capture
    // stays silent and the caller's watchdog will retry on the next gesture.
    if (ctx.state === 'suspended') {
      try { await ctx.resume(); } catch { /* keep trying on next acquire */ }
    }

    // If the assistant is still talking (pause requested), stay silent; a
    // later resume() (or the in-flight acquire re-checking paused) activates.
    if (!paused) {
      pcm = [];
      silenceStart = null;
      chunkSpeech = false;
      chunkStart = Date.now();
      active = true;
    }
    starting = false;
  } catch {
    if (!stopping) handlersRef?.onError?.('not-allowed');
    fullStop();
  }
}

export function startWhisperRecording(lang: string, handlers: WhisperSttHandlers) {
  if (active || starting) return;
  stopping = false;
  paused = false;
  langRef = lang;
  handlersRef = handlers;
  void acquireAndRun();
}

export function stopWhisperRecording() {
  if (active) {
    stopping = true;
    void finalize();
  } else if (starting) {
    fullStop();
  }
}

/**
 * Pause capture while the assistant speaks (its TTS would otherwise be
 * picked up, transcribed and sent back to Rasa). Discards in-flight chunks.
 */
export function pauseWhisperRecording() {
  if (!active && !starting) return;
  paused = true;
  generation++;
  active = false;
  pcm = [];
  silenceStart = null;
  chunkSpeech = false;
}

/**
 * Resume capture after the assistant has finished speaking. Safe to call even
 * while the mic is still being acquired (permission prompt): the in-flight
 * acquisition re-checks `paused` and activates once it's wired.
 */
export function resumeWhisperRecording() {
  if (stopping) return;
  paused = false;
  if (active) return;
  if (!wired || !ctx || !stream || !node || !source) {
    // Graph not wired yet (acquisition in flight) or lost → (re)acquire.
    void acquireAndRun();
    return;
  }
  pcm = [];
  silenceStart = null;
  chunkSpeech = false;
  chunkStart = Date.now();
  active = true;
}

export function isWhisperListening(): boolean {
  return active || starting;
}

/**
 * True when the audio graph is fully wired but capture is silently OFF and
 * not in a transient state — i.e. left parked after the assistant's TTS
 * failed to call resume(). Callers use this to self-heal hands-free mode.
 */
export function isWhisperStalled(): boolean {
  return wired && !active && !starting && !stopping && !paused;
}