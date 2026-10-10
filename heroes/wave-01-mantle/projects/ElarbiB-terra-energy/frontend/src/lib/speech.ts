import { LOCALES, type Lang } from '../i18n/dictionaries';

type SpeechRecognitionLike = {
  lang: string;
  interimResults: boolean;
  maxAlternatives: number;
  continuous: boolean;
  start: () => void;
  stop: () => void;
  abort: () => void;
  onresult: ((event: unknown) => void) | null;
  onend: (() => void) | null;
  onerror: ((event: { error?: string }) => void) | null;
};

/* ── helpers ────────────────────────────────────────────────────────── */

function getRecognitionCtor():
  | (new () => SpeechRecognitionLike)
  | undefined {
  if (typeof window === 'undefined') return undefined;
  const w = window as unknown as Record<string, unknown>;
  return (w.SpeechRecognition ?? w.webkitSpeechRecognition) as
    | (new () => SpeechRecognitionLike)
    | undefined;
}

export function isRecognitionSupported(): boolean {
  return getRecognitionCtor() !== undefined;
}

export function isSpeechSupported(): boolean {
  return typeof window !== 'undefined' && 'speechSynthesis' in window;
}

/**
 * Safari's webkitSpeechRecognition does not support continuous mode and
 * refuses to (re)start recognition outside a real user gesture. Auto-restart
 * there just makes the mic blink on/off. Chrome supports continuous + restart
 * from onend, so we keep hands-free there and fall back to push-to-talk on
 * Safari/iOS.
 */
const IS_SAFARI =
  typeof navigator !== 'undefined' &&
  /Safari/i.test(navigator.userAgent) &&
  !/Chrome|Chromium|CriOS/i.test(navigator.userAgent);

export const recognitionAutoRestart = !IS_SAFARI;

/** macOS Safari's webkitSpeechRecognition service is non-functional (iOS Safari is fine). */
export const IS_MACOS_SAFARI =
  IS_SAFARI &&
  /Macintosh|Mac OS X|Intel Mac/i.test(navigator.userAgent) &&
  !/iPhone|iPad|iPod/i.test(navigator.userAgent);

/**
 * Use the browser SpeechRecognition API, except on macOS Safari where the
 * service is unavailable — there we fall back to WebAudio + the local
 * Whisper bridge (see lib/whisperSTT.ts).
 */
export const useBrowserSpeech = isRecognitionSupported() && !IS_MACOS_SAFARI;

/* ── TTS (text-to-speech) ───────────────────────────────────────────── */

const PREFERRED_VOICES = [
  // Chrome / Edge – high-quality neural
  'Google US English', 'Google UK English Female', 'Google UK English Male',
  'Google Deutsch', 'Google français', 'Google Español',
  'Microsoft Aria Online (Natural)', 'Microsoft Guy Online (Natural)',
  'Microsoft Jenny Online (Natural)', 'Microsoft Hortense Online (Natural)',
  'Microsoft Helene Online (Natural)',
  // macOS / iOS
  'Samantha', 'Victoria', 'Karen', 'Daniel', 'Moira', 'Alex',
  'Amélie', 'Élodie', 'Audrey', 'Thomas', 'Yannick',
  'Anna', 'Helena', 'Jonas', 'Mikael',
  'Carmen', 'Diego', 'Monica', 'Paulina', 'Jorge',
  'Siri',
];

let cachedVoices: SpeechSynthesisVoice[] = [];

function loadVoices() {
  try {
    cachedVoices = window.speechSynthesis.getVoices();
  } catch {
    cachedVoices = [];
  }
}

if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
  loadVoices();
  window.speechSynthesis.onvoiceschanged = loadVoices;
}

function pickVoice(locale: string): SpeechSynthesisVoice | null {
  if (!cachedVoices.length) loadVoices();
  const primary = locale.split('-')[0].toLowerCase();
  const localeLower = locale.toLowerCase();

  // 1. Exact locale match (fr-FR == fr-FR)
  const exact = cachedVoices.find(
    (v) => v.lang && v.lang.toLowerCase() === localeLower,
  );
  if (exact) return exact;

  // 2. Preferred voice matching locale prefix
  const langMatch = cachedVoices.filter(
    (v) => v.lang && v.lang.toLowerCase().startsWith(primary),
  );
  const preferred = langMatch.find((v) => {
    const n = v.name.toLowerCase();
    return PREFERRED_VOICES.some((p) => n.includes(p.toLowerCase()));
  });
  if (preferred) return preferred;

  // 3. Any voice for this language
  if (langMatch.length) return langMatch[0];

  // 4. Fallback to first available voice
  return cachedVoices[0] ?? null;
}

export function speak(
  text: string,
  lang: string,
  onStart?: () => void,
  onEnd?: () => void,
) {
  if (!isSpeechSupported() || !text.trim()) {
    onStart?.();
    onEnd?.();
    return;
  }
  try {
    const synth = window.speechSynthesis;
    synth.cancel();
    const locale = LOCALES[lang as Lang] ?? LOCALES.fr;
    const utter = new SpeechSynthesisUtterance(text);
    utter.lang = locale;
    utter.rate = 0.92;   // slightly slower for clarity
    utter.pitch = 1;
    utter.volume = 1;     // max volume
    const voice = pickVoice(locale);
    if (voice) utter.voice = voice;
    utter.onstart = () => onStart?.();
    utter.onend = () => onEnd?.();
    utter.onerror = () => onEnd?.();
    synth.speak(utter);
    // Chrome workaround: after a cancel(), the speech queue can stall.
    // resume() un-sticks it so the utterance actually starts.
    try { synth.resume(); } catch { /* ignore */ }
  } catch {
    onStart?.();
    onEnd?.();
  }
}

export function stopSpeaking() {
  if (!isSpeechSupported()) return;
  try {
    window.speechSynthesis.cancel();
  } catch {
    /* ignore */
  }
}

/** True while speechSynthesis is still producing audio (or stuck). */
export function isSpeaking(): boolean {
  if (!isSpeechSupported()) return false;
  try {
    return window.speechSynthesis.speaking === true;
  } catch {
    return false;
  }
}

/* ── Speech recognition (microphone) ────────────────────────────────── */

let recognizer: SpeechRecognitionLike | null = null;
let stopping = false;
let _onEnd: (() => void) | null = null;
let lastRecognitionActivity = 0;

/** Returns true if the recognition session is currently active. */
export function isListening(): boolean {
  return recognizer !== null && !stopping;
}

/**
 * Milliseconds since the recognizer last delivered a result (final or
 * interim). When the recognizer is not running, returns 0. Chrome's
 * continuous mode can silently freeze (~1 min of silence, no `onend` fired);
 * callers use this to detect the zombie state and restart recognition.
 */
export function recognitionStalledMs(): number {
  if (recognizer === null || stopping) return 0;
  return Date.now() - lastRecognitionActivity;
}

export function startListening(
  lang: string,
  handlers: {
    onTranscript: (text: string) => void;
    onEnd: () => void;
    onError?: (error: string) => void;
    onInterim?: (text: string) => void;
  },
) {
  if (recognizer) return;

  const Ctor = getRecognitionCtor();
  if (!Ctor) {
    handlers.onError?.('unsupported');
    handlers.onEnd();
    return;
  }

  _onEnd = handlers.onEnd;

  try {
    const rec = new Ctor();
    const locale = LOCALES[lang as Lang] ?? LOCALES.fr;
    rec.lang = locale;
    rec.interimResults = true;
    rec.maxAlternatives = 1;
    rec.continuous = recognitionAutoRestart;
    stopping = false;
    lastRecognitionActivity = Date.now();

    rec.onresult = (event: unknown) => {
      lastRecognitionActivity = Date.now();
      const ev = event as {
        resultIndex: number;
        results: ArrayLike<ArrayLike<{ isFinal: boolean; transcript: string }>>;
      };
      let interim = '';
      for (let i = ev.resultIndex; i < ev.results.length; i++) {
        const result = ev.results[i];
        const line = result[0];
        if (!line) continue;
        if (line.isFinal) {
          const transcript = line.transcript.trim();
          if (transcript) handlers.onTranscript(transcript);
        } else {
          interim += line.transcript;
        }
      }
      const interimText = interim.trim();
      if (interimText) handlers.onInterim?.(interimText);
    };

    rec.onerror = (ev) => {
      const err = ev?.error ?? 'recognition_error';

      // Fatal errors: permissions / not supported
      if (err === 'not-allowed' || err === 'service-not-allowed') {
        handlers.onError?.(err);
        recognizer = null;
        stopping = true;
        handlers.onEnd?.();
        return;
      }

      // Recoverable errors: restart after a short delay (Chrome only).
      // Safari can't restart without a fresh gesture → stop and let the
      // user tap the mic button again.
      if (err === 'no-speech' || err === 'aborted' || err === 'network' || err === 'recognition_error') {
        if (!recognitionAutoRestart) {
          handlers.onEnd?.();
          return;
        }
        // Don't restart if we're intentionally stopping
        if (stopping) return;
        // Restart with a small delay to avoid Chrome race condition
        setTimeout(() => {
          if (!stopping && recognizer === null) {
            try {
              const fresh = new Ctor();
              fresh.lang = locale;
              fresh.interimResults = true;
              fresh.maxAlternatives = 1;
              fresh.continuous = true;
              fresh.onresult = rec.onresult;
              fresh.onerror = rec.onerror;
              fresh.onend = rec.onend;
              fresh.start();
              recognizer = fresh;
              lastRecognitionActivity = Date.now();
            } catch {
              handlers.onEnd?.();
            }
          }
        }, 400);
        return;
      }

      // Unknown error
      console.warn('Speech recognition error:', err);
    };

    rec.onend = () => {
      recognizer = null;
      if (stopping) {
        handlers.onEnd?.();
        return;
      }
      if (!recognitionAutoRestart) {
        // Safari: let the UI go back to the push-to-talk state.
        handlers.onEnd?.();
        return;
      }
      // Auto-restart after a brief pause (Chrome kills sessions after ~30s silence)
      setTimeout(() => {
        if (!stopping && recognizer === null) {
          try {
            const fresh = new Ctor();
            fresh.lang = locale;
            fresh.interimResults = true;
            fresh.maxAlternatives = 1;
            fresh.continuous = true;
            fresh.onresult = rec.onresult;
            fresh.onerror = rec.onerror;
            fresh.onend = rec.onend;
            fresh.start();
            recognizer = fresh;
            lastRecognitionActivity = Date.now();
          } catch {
            handlers.onEnd?.();
          }
        }
      }, 300);
    };

    rec.start();
    recognizer = rec;
  } catch {
    handlers.onError?.('start_failed');
    handlers.onEnd?.();
  }
}

export function stopListening() {
  stopping = true;
  _onEnd = null;
  lastRecognitionActivity = 0;
  try {
    recognizer?.stop();
  } catch {
    /* ignore */
  }
  recognizer = null;
}
