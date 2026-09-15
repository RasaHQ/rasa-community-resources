import React, { useState, useRef, useEffect, useCallback } from 'react';
import { XIcon, SearchIcon, LayersIcon, CompareIcon, Volume2Icon, VolumeXIcon } from '../ui/icons';
import { S } from '../../theme';
import { useI18n } from '../../i18n/LanguageContext';
import { sendChat } from '../../services/api';
import { buildAnalysisContext } from '../../lib/analysisContext';
import { speak, stopSpeaking, stopListening, isListening, isSpeaking, recognitionAutoRestart, recognitionStalledMs } from '../../lib/speech';
import { isWhisperStalled } from '../../lib/whisperSTT';
import VoiceRecorder, { VoiceRecorderHandle } from './VoiceRecorder';

// Minimal Terra mark (spark + orbit) replacing any emoji.
function TerraMark(props: React.SVGProps<SVGSVGElement>) {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" {...props}>
      <circle cx="12" cy="12" r="3" />
      <path d="M12 2v3M12 19v3M2 12h3M19 12h3M4.9 4.9l2.1 2.1M17 17l2.1 2.1M19.1 4.9L17 7M7 17l-2.1 2.1" />
    </svg>
  );
}

function UserMark(props: React.SVGProps<SVGSVGElement>) {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" {...props}>
      <circle cx="12" cy="8" r="4" />
      <path d="M4 21c0-4.5 3.6-7 8-7s8 2.5 8 7" />
    </svg>
  );
}

// Hard cap on how long the anti-feedback hold may keep the mic muted. The
// hold is normally released by speechSynthesis' onend/onerror or by the
// watchdog polling isSpeaking(); when both lie (Chrome can report speaking=true
// forever after a cancel()), this bound guarantees the user's voice flows again.
const TTS_HOLD_CAP_MS = 30000;
const TTS_POLL_INTERVAL_MS = 2000;
// Chrome's continuous recognizer can silently freeze after ~1 min without
// firing onend. If it's been idle this long and Terra isn't talking, restart it.
const RECOGNIZER_IDLE_RESTART_MS = 40000;
// Nudge cadence while the panel is open.
const MIC_HEALTH_INTERVAL_MS = 5000;

interface VoiceAssistantOrbProps {
  onAction?: (action: string, params: any) => void;
  onTranscript?: (text: string) => void;
  mapRef?: React.RefObject<any>;
  siteResult?: any;
  comparisonResult?: any;
}

export default function VoiceAssistantOrb({
  onTranscript,
  siteResult,
  comparisonResult,
}: VoiceAssistantOrbProps) {
  const { t, lang } = useI18n();
  const [isOpen, setIsOpen] = useState(false);
  const [isMuted, setIsMuted] = useState(false);
  const [orbState, setOrbState] = useState<'idle' | 'listening' | 'processing' | 'speaking'>('idle');
  const [messages, setMessages] = useState<Array<{ role: 'user' | 'assistant'; content: string }>>([]);
  const [inputText, setInputText] = useState('');
  const [hasWelcomed, setHasWelcomed] = useState(false);
  const orbRef = useRef<HTMLDivElement>(null);
  const animationFrameRef = useRef<number | null>(null);
  const busyRef = useRef(false);
  const [orbScale, setOrbScale] = useState(1);
  const [orbGlow, setOrbGlow] = useState(0);
  const [orbPosition, setOrbPosition] = useState({ x: 0, y: 0 });
  const [orbSize, setOrbSize] = useState({ width: 56, height: 56 });

  const isDraggingRef = useRef(false);
  const dragOffsetRef = useRef({ x: 0, y: 0 });
  const dragStartRef = useRef({ x: 0, y: 0 });
  const didDragRef = useRef(false);
  const micRef = useRef<VoiceRecorderHandle>(null);
  const micListeningRef = useRef(false);
  const ignoreSpeechRef = useRef(false);
  const speechWatchdogRef = useRef<number | null>(null);
  const hardHoldRef = useRef<number | null>(null);
  const pendingTextRef = useRef('');
  const [micHint, setMicHint] = useState('');
  const [interimText, setInterimText] = useState('');

  // ── position & resize ──────────────────────────────────────────────
  useEffect(() => {
    const updatePosition = () => {
      setOrbPosition({
        x: window.innerWidth - orbSize.width - 24,
        y: window.innerHeight - orbSize.height - 24,
      });
    };
    updatePosition();
    window.addEventListener('resize', updatePosition);
    return () => window.removeEventListener('resize', updatePosition);
  }, [orbSize.width, orbSize.height]);

  // ── drag ───────────────────────────────────────────────────────────
  const handleMouseMove = useCallback((e: MouseEvent) => {
    if (!isDraggingRef.current) return;
    didDragRef.current = true;
    const newX = e.clientX - dragOffsetRef.current.x;
    const newY = e.clientY - dragOffsetRef.current.y;
    const maxX = window.innerWidth - orbSize.width;
    const maxY = window.innerHeight - orbSize.height;
    setOrbPosition({
      x: Math.max(0, Math.min(newX, maxX)),
      y: Math.max(0, Math.min(newY, maxY)),
    });
  }, []);

  const handleMouseUp = useCallback(() => {
    isDraggingRef.current = false;
    dragOffsetRef.current = { x: 0, y: 0 };
    document.removeEventListener('mousemove', handleMouseMove);
    document.removeEventListener('mouseup', handleMouseUp);
  }, [handleMouseMove]);

  // ── orb animation ──────────────────────────────────────────────────
  useEffect(() => {
    let frame = 0;
    const animate = () => {
      frame++;
      if (orbState === 'listening') {
        setOrbScale(1 + Math.sin(frame * 0.1) * 0.05);
        setOrbGlow(0.8 + Math.sin(frame * 0.15) * 0.2);
      } else if (orbState === 'processing') {
        setOrbScale(1 + Math.sin(frame * 0.2) * 0.03);
        setOrbGlow(0.6 + Math.sin(frame * 0.1) * 0.3);
      } else if (orbState === 'speaking') {
        setOrbScale(1 + Math.sin(frame * 0.15) * 0.04);
        setOrbGlow(0.7 + Math.sin(frame * 0.12) * 0.2);
      } else {
        setOrbScale(1 + Math.sin(frame * 0.02) * 0.02);
        setOrbGlow(0.5 + Math.sin(frame * 0.03) * 0.2);
      }
      animationFrameRef.current = requestAnimationFrame(animate);
    };
    animationFrameRef.current = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(animationFrameRef.current!);
  }, [orbState]);

  // ── ensure mic is alive (called periodically while panel is open) ──
  const ensureMicRunning = useCallback(() => {
    if (!isOpen || busyRef.current || isMuted) return;
    // Terra still talking → the echo guard keeps capture muted on purpose.
    if (ignoreSpeechRef.current) return;

    // Whisper backend: if capture got left paused after Terra's TTS finished,
    // reactivate it. resume() is idempotent and a safe no-op when running.
    if (micListeningRef.current && isWhisperStalled()) {
      try { micRef.current?.resume?.(); } catch { /* ignore */ }
    }

    // Browser backend (Chrome): a recognizer can silently freeze (no onend,
    // no results) after ~1 min. If it's been idle too long, force a restart.
    if (recognitionAutoRestart && micListeningRef.current && isListening()) {
      if (recognitionStalledMs() > RECOGNIZER_IDLE_RESTART_MS) {
        try { micRef.current?.stop(); } catch { /* ignore */ }
      }
    }

    // Gone entirely while it should be running → restart (Chrome only;
    // Safari keeps its push-to-talk semantics and never reopens the mic).
    if (!micListeningRef.current && recognitionAutoRestart) {
      try { micRef.current?.start(); } catch { /* ignore */ }
    }
  }, [isOpen, isMuted]);

  // Ping mic every 5s while panel is open to recover from Chrome auto-stop
  useEffect(() => {
    if (!isOpen) return;
    const id = setInterval(ensureMicRunning, MIC_HEALTH_INTERVAL_MS);
    return () => clearInterval(id);
  }, [isOpen, ensureMicRunning]);

  // ── state helpers ──────────────────────────────────────────────────
  const resetState = () => {
    setOrbState(micListeningRef.current ? 'listening' : 'idle');
  };

  const clearSpeechWatchdog = () => {
    if (speechWatchdogRef.current !== null) {
      clearTimeout(speechWatchdogRef.current);
      speechWatchdogRef.current = null;
    }
    if (hardHoldRef.current !== null) {
      clearTimeout(hardHoldRef.current);
      hardHoldRef.current = null;
    }
  };

  /**
   * Idempotent: ends the anti-feedback hold and hands the mic back. Safe to
   * call from any number of sources (utter.onend, utter.onerror, watchdog,
   * hard cap) — the first release wins, later ones are no-ops.
   */
  const releaseMicHold = () => {
    clearSpeechWatchdog();
    ignoreSpeechRef.current = false;
    setInterimText('');
    resetState();
    try { micRef.current?.resume?.(); } catch { /* ignore */ }
    ensureMicRunning();
  };

  // Chrome sometimes never fires utterance.onend (speech gets stuck).
  // Watchdog: as long as synth reports it's speaking, keep ignoring the
  // mic; as soon as it isn't, release the ignore flag so user speech flows.
  // A hard cap guarantees the release even if isSpeaking() lies (Chrome).
  const armSpeechWatchdog = () => {
    clearSpeechWatchdog();
    const hardCap = window.setTimeout(releaseMicHold, TTS_HOLD_CAP_MS);
    hardHoldRef.current = hardCap;
    const check = () => {
      if (isSpeaking()) {
        speechWatchdogRef.current = window.setTimeout(check, TTS_POLL_INTERVAL_MS);
        return;
      }
      clearTimeout(hardCap);
      hardHoldRef.current = null;
      releaseMicHold();
    };
    speechWatchdogRef.current = window.setTimeout(check, TTS_POLL_INTERVAL_MS);
  };

  const addAssistantMessage = (content: string, speakIt = true) => {
    setMessages((prev) => [...prev, { role: 'assistant', content }]);
    if (!speakIt || isMuted) {
      resetState();
      return;
    }
    stopSpeaking();
    setInterimText('');
    ignoreSpeechRef.current = true;      // ignore our own TTS in mic
    // Whisper backend: freeze capture while we answer so our TTS is never
    // transcribed back to Rasa; resume once speech is over.
    try { micRef.current?.pause?.(); } catch { /* ignore */ }
    speak(
      content,
      lang,
      () => setOrbState('speaking'),
      () => releaseMicHold(),
    );
    armSpeechWatchdog();
  };

  const handleUserText = async (raw: string) => {
    const text = raw.trim();
    if (!text) return;

    // A turn is already in flight (Rasa tool calls take seconds). In
    // hands-free mode the user often keeps talking while the orb shows
    // 'processing'; queue the newest utterance so it isn't silently dropped.
    if (busyRef.current) {
      pendingTextRef.current = text;
      return;
    }

    const userMessage = { role: 'user' as const, content: text };
    const history = messages
      .filter((m) => m.role === 'user' || m.role === 'assistant')
      .map((m) => ({ role: m.role, content: m.content }));

    busyRef.current = true;
    setMessages((prev) => [...prev, userMessage]);
    onTranscript?.(text);
    setOrbState('processing');

    try {
      const context = buildAnalysisContext(siteResult, comparisonResult);
      const reply = await sendChat(text, history, context);
      addAssistantMessage(reply);
    } catch (error) {
      console.error('Rasa chat error:', error);
      addAssistantMessage(t('ai.error'));
    } finally {
      busyRef.current = false;
      const pending = pendingTextRef.current;
      if (pending && pending !== text) {
        pendingTextRef.current = '';
        void handleUserTextRef.current(pending);
      }
    }
  };

  const handleUserTextRef = useRef(handleUserText);
  useEffect(() => { handleUserTextRef.current = handleUserText; });

  const handleRecorderTranscript = useCallback((text: string) => {
    if (ignoreSpeechRef.current) return;
    setInterimText('');
    if (text.trim()) handleUserTextRef.current(text);
  }, []);

  const handleRecorderInterim = useCallback((text: string) => {
    if (ignoreSpeechRef.current) return;
    setInterimText(text);
  }, []);

  const handleMicListening = useCallback((listening: boolean) => {
    micListeningRef.current = listening;
    setMicHint('');
    if (listening) {
      setOrbState('listening');
    } else {
      setOrbState((prev) => (prev === 'listening' ? 'idle' : prev));
      // Safari push-to-talk: after a mic session ends, nudge the user to
      // tap the mic button again to reply.
      if (!recognitionAutoRestart && isOpen && !busyRef.current && !isMuted) {
        setMicHint(t('ai.micRetry'));
      }
    }
  }, [t, isOpen, isMuted]);

  const handleMicError = useCallback(
    (err: string) => {
      console.error('Voice error:', err);
      if (err === 'not-allowed' || err === 'service-not-allowed') {
        setMicHint(t('ai.micRetry'));
      } else if (err !== 'start_failed') {
        // start_failed can happen on auto-restart; don't alarm user
        setMicHint(t('ai.micUnsupported'));
      }
    },
    [t],
  );

  const handleInputSubmit = (e?: React.FormEvent) => {
    e?.preventDefault();
    if (!inputText.trim() || busyRef.current) return;
    const text = inputText;
    setInputText('');
    handleUserText(text);
  };

  // ── ORB CLICK: open panel + start mic + speak welcome ──
  const handleOrbClick = () => {
    if (didDragRef.current) {
      didDragRef.current = false;
      return;
    }
    if (busyRef.current) return;
    if (!isOpen) {
      setIsOpen(true);

      // Start mic SYNCHRONOUSLY inside the user gesture (Chrome refuses
      // SpeechRecognition.start() from a rAF/timeout/async callback).
      // The panel is always mounted, so the ref is already available.
      try { micRef.current?.start(); } catch { /* ignore */ }

      if (!hasWelcomed) {
        setHasWelcomed(true);
        // Speak welcome but ignore mic picking up our own TTS
        stopSpeaking();
        setInterimText('');
        ignoreSpeechRef.current = true;
        // Whisper backend: freeze capture while we talk so our welcome is
        // never transcribed back; resume once it's over.
        try { micRef.current?.pause?.(); } catch { /* ignore */ }
        speak(
          t('ai.welcome'),
          lang,
          () => setOrbState('speaking'),
          () => releaseMicHold(),
        );
        armSpeechWatchdog();
        setMessages((prev) => [...prev, { role: 'assistant', content: t('ai.welcome') }]);
      }
    } else {
      setIsOpen(false);
    }
  };

  const toggleMute = () => {
    if (!isMuted) {
      stopSpeaking();
      releaseMicHold();
    }
    setIsMuted((m) => !m);
  };

  // Stop mic when panel closes
  useEffect(() => {
    if (!isOpen) {
      micRef.current?.stop();
      clearSpeechWatchdog();
      ignoreSpeechRef.current = false;
      setInterimText('');
    }
  }, [isOpen]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      stopSpeaking();
      stopListening();
      clearSpeechWatchdog();
      if (animationFrameRef.current) cancelAnimationFrame(animationFrameRef.current);
    };
  }, []);

  const statusText =
    orbState === 'listening'
      ? t('ai.listening')
      : orbState === 'processing'
      ? t('ai.processing')
      : orbState === 'speaking'
      ? t('ai.speaking')
      : t('ai.ready');

  // Panel position: dock the chat next to the orb wherever it is dragged.
  const PANEL_W = 380;
  const PANEL_MAX_H = () => window.innerHeight * 0.6;
  const PANEL_GAP = 12;
  let panelLeft: number;
  let panelTop: number;
  const orbCenterY = orbPosition.y + orbSize.height / 2;
  // Preferred side: left of the orb, else right; clamp within the viewport.
  {
    const leftOfOrb = orbPosition.x - PANEL_W - PANEL_GAP;
    const rightOfOrb = orbPosition.x + orbSize.width + PANEL_GAP;
    const maxLeft = window.innerWidth - PANEL_W - 12;
    panelLeft = leftOfOrb >= 12 ? leftOfOrb : Math.min(rightOfOrb, maxLeft);
    panelLeft = Math.max(12, Math.min(panelLeft, maxLeft));
  }
  {
    // Vertically centre on the orb; keep inside the viewport.
    const maxTop = window.innerHeight - PANEL_MAX_H() - 12;
    panelTop = Math.min(Math.max(12, orbCenterY - PANEL_MAX_H() / 2), Math.max(12, maxTop));
  }

  return (
    <>
      {/* Persistent Orb */}
      <div
        ref={orbRef}
        style={{
          position: 'fixed',
          left: `${orbPosition.x}px`,
          top: `${orbPosition.y}px`,
          zIndex: 10000,
          pointerEvents: 'auto',
        }}
      >
        <div
          style={{
            width: 56,
            height: 56,
            borderRadius: '50%',
            position: 'relative',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            cursor: isDraggingRef.current ? 'grabbing' : 'grab',
            transform: `scale(${orbScale})`,
            transition: 'transform 0.1s ease-out',
            overflow: 'visible',
            userSelect: 'none',
            flexShrink: 0,
          }}
          onClick={handleOrbClick}
          onMouseDown={(e) => {
            if (e.button === 0 && !busyRef.current) {
              didDragRef.current = false;
              const rect = orbRef.current?.getBoundingClientRect();
              if (rect) {
                dragOffsetRef.current = { x: e.clientX - rect.left, y: e.clientY - rect.top };
                isDraggingRef.current = true;
                document.addEventListener('mousemove', handleMouseMove);
                document.addEventListener('mouseup', handleMouseUp);
              }
            }
          }}
          onMouseEnter={() => !isDraggingRef.current && setOrbScale((s) => s * 1.05)}
          onMouseLeave={() => !isDraggingRef.current && setOrbScale(1)}
        >
          {/* Chakra aura (Rasengan) — blue energy halo rotating slowly */}
          <div style={{
            position: 'absolute', inset: -16, borderRadius: '50%',
            background: 'conic-gradient(from 0deg, #0ea5e9, #38bdf8, #7dd3fc, #e0f2fe, #38bdf8, #0ea5e9)',
            filter: 'blur(16px)',
            opacity: orbState === 'idle' ? 0.9 : 1,
            animation: orbState === 'processing' ? 'spin 4s linear infinite' : 'spin 14s linear infinite',
            transition: 'opacity 0.4s',
          }} />
          {/* Chakra shell — bright white core fading to deep blue, like the sphere Naruto spins */}
          <div style={{
            position: 'absolute', inset: 0, borderRadius: '50%',
            background: `
              radial-gradient(circle at 30% 26%, rgba(255,255,255,0.55), transparent 42%),
              radial-gradient(circle at 50% 55%, #ffffff 0%, #d6f0ff 16%, #7dd3fc 42%, #2563eb 75%, #1e40af 100%)
            `,
            border: '1px solid rgba(147,197,253,0.65)',
            boxShadow: `
              0 0 ${20 + orbGlow * 30}px rgba(56,189,248,${0.55 + orbGlow * 0.35}),
              0 0 ${42 + orbGlow * 45}px rgba(37,99,235,${0.4 + orbGlow * 0.35}),
              inset 0 1px 10px rgba(255,255,255,0.5)
            `,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
            {orbState === 'listening' ? (
              <Volume2Icon style={{ width: 18, height: 18, color: '#bae6fd', animation: 'pulse 0.8s infinite', filter: 'drop-shadow(0 0 6px rgba(186,230,253,0.95))' }} />
            ) : orbState === 'processing' ? (
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#bae6fd" strokeWidth="2" style={{ animation: 'spin 1s linear infinite', filter: 'drop-shadow(0 0 6px rgba(186,230,253,0.95))' }}>
                <circle cx="12" cy="12" r="10" strokeOpacity="0.25" />
                <path d="M12 2a10 10 0 0 1 10 10" strokeLinecap="round" />
              </svg>
            ) : orbState === 'speaking' ? (
              <Volume2Icon style={{ width: 18, height: 18, color: '#e0f2fe', animation: 'pulse 0.6s infinite', filter: 'drop-shadow(0 0 6px rgba(224,242,254,0.95))' }} />
            ) : (
              <span style={{
                width: 9, height: 9, borderRadius: '50%',
                background: 'radial-gradient(circle at 35% 35%, #ffffff, #e0f2fe 60%, #7dd3fc)',
                boxShadow: '0 0 12px rgba(255,255,255,0.95), 0 0 26px rgba(125,211,252,0.7)',
                animation: 'pulse 2s infinite',
              }} />
            )}
          </div>
          {/* Swirling chakra streams wrapping around the sphere */}
          <div style={{
            position: 'absolute', inset: 2, borderRadius: '50%',
            background: 'conic-gradient(from 90deg, transparent 0deg, rgba(224,242,254,0.55) 50deg, transparent 115deg, rgba(224,242,254,0.40) 205deg, transparent 265deg)',
            filter: 'blur(0.5px)',
            mixBlendMode: 'screen',
            animation: 'spin 6s linear infinite',
            opacity: orbState === 'idle' ? 0.8 : 1,
          }} />
          {/* Activity arc */}
          <div style={{
            position: 'absolute', inset: -5, borderRadius: '50%',
            borderTop: `2px solid ${orbState !== 'idle' ? 'rgba(224,242,254,0.8)' : 'transparent'}`,
            borderRight: '2px solid transparent',
            borderBottom: '2px solid transparent',
            borderLeft: '2px solid transparent',
            animation: orbState !== 'idle' ? 'spin 1.4s linear infinite' : 'none',
            opacity: orbState !== 'idle' ? 0.6 : 0,
            transition: 'opacity 0.3s',
          }} />
        </div>

        {/* Tooltip */}
        <div style={{
          position: 'absolute', bottom: 90, right: 0,
          background: S.card, border: `1px solid ${S.border}`, borderRadius: 8,
          padding: '8px 12px', fontSize: '0.65rem', color: S.text2,
          whiteSpace: 'nowrap', boxShadow: '0 8px 32px rgba(0,0,0,0.4)',
          opacity: isOpen ? 0 : 1, pointerEvents: 'none',
          transition: 'opacity 0.2s, transform 0.2s',
          transform: isOpen ? 'translateY(8px)' : 'translateY(0)',
        }}>
          {t('ai.open')}
        </div>
      </div>

      {/* Floating Panel — always mounted so micRef exists for gestures */}
      <div
        style={{
          position: 'fixed', left: panelLeft, top: panelTop, zIndex: 9999,
          width: PANEL_W, maxWidth: 'calc(100vw - 24px)', maxHeight: '60vh',
          background: S.bg, border: `1px solid ${S.border2}`, borderRadius: 16,
          boxShadow: '0 20px 60px rgba(0,0,0,0.6)',
          display: isOpen ? 'flex' : 'none',
          flexDirection: 'column', overflow: 'hidden',
          animation: isOpen ? 'slideUp 0.3s cubic-bezier(0.16, 1, 0.3, 1)' : 'none',
        }}>
          <style>{`
            @keyframes slideUp {
              from { opacity: 0; transform: translateY(20px) scale(0.95); }
              to { opacity: 1; transform: translateY(0) scale(1); }
            }
            @keyframes spin { to { transform: rotate(360deg); } }
            @keyframes pulse { 0%, 100% { opacity: 1; transform: scale(1); } 50% { opacity: 0.5; transform: scale(1.1); } }
          `}</style>

          {/* Header */}
          <div style={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            padding: '12px 16px', background: `${S.surface}ee`,
            borderBottom: `1px solid ${S.border}`, backdropFilter: 'blur(10px)',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <div style={{
                width: 32, height: 32, borderRadius: '50%',
                background: `linear-gradient(135deg, ${S.solar}, ${S.wind})`,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                color: '#0a0e17',
              }}>
                <TerraMark style={{ width: 16, height: 16 }} />
              </div>
              <div>
                <div style={{
                  fontFamily: "'Space Grotesk', sans-serif",
                  fontSize: '0.75rem', fontWeight: 600, color: S.text,
                }}>{t('ai.assistant')}</div>
                <div style={{ fontSize: '0.55rem', color: S.text3 }}>{statusText}</div>
              </div>
            </div>
            <div style={{ display: 'flex', gap: 6 }}>
              <button onClick={toggleMute} style={{
                width: 28, height: 28, borderRadius: 8,
                background: isMuted ? S.text3 : S.surface,
                border: `1px solid ${S.border}`,
                color: isMuted ? S.text3 : S.text,
                cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center',
              }} aria-label={isMuted ? 'Activate sound' : 'Mute'}>
                {isMuted ? <VolumeXIcon style={{ width: 14, height: 14 }} /> : <Volume2Icon style={{ width: 14, height: 14 }} />}
              </button>
              <button onClick={() => setIsOpen(false)} style={{
                width: 28, height: 28, borderRadius: 8, background: S.surface,
                border: `1px solid ${S.border}`, color: S.text2,
                cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center',
              }} aria-label="Close">
                <XIcon style={{ width: 14, height: 14 }} />
              </button>
            </div>
          </div>

          {/* Messages */}
          <div style={{
            flex: 1, overflowY: 'auto', padding: 16,
            display: 'flex', flexDirection: 'column', gap: 12,
          }}>
            {messages.length === 0 && (
              <div style={{ textAlign: 'center', padding: '24px 16px', color: S.text3 }}>
                <div style={{
                  width: 48, height: 48, margin: '0 auto 12px', borderRadius: '50%',
                  background: `${S.wind}15`, border: `1px solid ${S.wind}25`,
                  color: S.wind, display: 'flex', alignItems: 'center', justifyContent: 'center',
                }}>
                  <TerraMark style={{ width: 22, height: 22 }} />
                </div>
                <p style={{ fontWeight: 600, marginBottom: 4 }}>{t('ai.welcome')}</p>
                <p style={{ fontSize: '0.75rem', lineHeight: 1.5 }}>{t('ai.emptyPrompt')}</p>
              </div>
            )}

            {messages.map((msg, i) => (
              <div key={i} style={{
                display: 'flex', gap: 10, alignItems: 'flex-start',
                flexDirection: msg.role === 'user' ? 'row-reverse' : 'row',
              }}>
                <div style={{
                  width: 28, height: 28, borderRadius: '50%', flexShrink: 0,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  background: msg.role === 'user' ? `${S.text}12` : `linear-gradient(135deg, ${S.solar}, ${S.wind})`,
                  color: msg.role === 'user' ? S.text2 : '#0a0e17',
                }}>
                  {msg.role === 'user'
                    ? <UserMark style={{ width: 14, height: 14 }} />
                    : <TerraMark style={{ width: 14, height: 14 }} />}
                </div>
                <div style={{
                  maxWidth: '75%', padding: '10px 14px',
                  borderRadius: msg.role === 'user' ? '16px 16px 4px 16px' : '16px 16px 16px 4px',
                  background: msg.role === 'user' ? `${S.solar}20` : S.card,
                  border: `1px solid ${msg.role === 'user' ? `${S.solar}40` : S.border}`,
                  color: S.text, fontSize: '0.75rem', lineHeight: 1.5,
                  whiteSpace: 'pre-wrap',
                }}>
                  {msg.content}
                </div>
              </div>
            ))}

            {interimText && (
              <div style={{
                display: 'flex', gap: 10, alignItems: 'flex-start',
                flexDirection: 'row-reverse',
              }}>
                <div style={{
                  maxWidth: '75%', padding: '10px 14px',
                  borderRadius: '16px 16px 4px 16px',
                  background: `${S.solar}0d`,
                  border: `1px dashed ${S.solar}40`,
                  color: S.text2, fontSize: '0.75rem', lineHeight: 1.5,
                  fontStyle: 'italic',
                }}>
                  {interimText}
                </div>
              </div>
            )}

            <div ref={(el) => el?.scrollIntoView({ behavior: 'smooth' })} />
          </div>

          {/* Quick Actions */}
          <div style={{
            padding: '12px 16px', borderTop: `1px solid ${S.border}`,
            background: `${S.surface}aa`, display: 'flex', gap: 8,
            flexWrap: 'wrap', justifyContent: 'center',
          }}>
            <button onClick={() => handleUserText(t('ai.tabAnalyze'))} className="quick-action">
              <SearchIcon style={{ width: 14, height: 14 }} />
              <span>{t('ai.tabAnalyze')}</span>
            </button>
            <button onClick={() => handleUserText(t('ai.tabCompare'))} className="quick-action">
              <CompareIcon style={{ width: 14, height: 14 }} />
              <span>{t('ai.tabCompare')}</span>
            </button>
            <button onClick={() => handleUserText(t('ai.tabInfo'))} className="quick-action">
              <LayersIcon style={{ width: 14, height: 14 }} />
              <span>{t('ai.tabInfo')}</span>
            </button>
            <button onClick={() => handleUserText(t('ai.tabHelp'))} className="quick-action">
              <SearchIcon style={{ width: 14, height: 14 }} />
              <span>{t('ai.tabHelp')}</span>
            </button>
            <style>{`
              .quick-action {
                display: flex; align-items: center; gap: 6;
                padding: 6px 12px; background: ${S.surface};
                border: 1px solid ${S.border}; border-radius: 20px;
                color: ${S.text2}; font-size: 0.6rem;
                font-family: 'JetBrains Mono', monospace;
                cursor: pointer; transition: all 0.15s;
              }
              .quick-action:hover {
                background: ${S.solar}15; border-color: ${S.solar}40; color: ${S.solar};
              }
            `}</style>
          </div>

          {/* Input row */}
          <form
            onSubmit={handleInputSubmit}
            style={{
              position: 'relative', display: 'flex', gap: 8, alignItems: 'center',
              padding: '10px 12px', borderTop: `1px solid ${S.border}`, background: S.surface,
            }}
          >
            {micHint && (
              <div style={{
                position: 'absolute', bottom: 62, left: 12, right: 12,
                background: `${S.wind}15`, border: `1px solid ${S.wind}40`,
                color: S.wind, borderRadius: 8, padding: '6px 10px',
                fontSize: '0.6rem', textAlign: 'center',
              }}>
                {micHint}
              </div>
            )}
            <VoiceRecorder
              ref={micRef}
              onTranscript={handleRecorderTranscript}
              onError={handleMicError}
              onListeningChange={handleMicListening}
              onInterim={handleRecorderInterim}
            />
            <input
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              placeholder={t('chat.placeholder')}
              style={{
                flex: 1, background: S.bg, border: `1px solid ${S.border}`,
                borderRadius: 8, padding: '8px 12px', color: S.text,
                fontSize: '0.7rem', fontFamily: "'JetBrains Mono', monospace", outline: 'none',
              }}
            />
            <button
              type="submit"
              disabled={!inputText.trim() || orbState === 'processing'}
              style={{
                width: 34, height: 34, flexShrink: 0,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                background: S.solar, border: 'none', color: '#0a0e17',
                cursor: 'pointer', borderRadius: 8,
                opacity: inputText.trim() && orbState !== 'processing' ? 1 : 0.5,
                transition: 'all 0.15s',
              }}
              aria-label="Send"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <line x1="22" y1="2" x2="11" y2="13" />
                <polygon points="22 2 15 22 11 13 2 9 22 2" />
              </svg>
            </button>
          </form>
      </div>

      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
        @keyframes pulse {
          0%, 100% { opacity: 1; transform: scale(1); }
          50% { opacity: 0.6; transform: scale(1.1); }
        }
      `}</style>
    </>
  );
}
