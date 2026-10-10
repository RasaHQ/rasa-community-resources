import React, { useState, useCallback, useRef, forwardRef, useImperativeHandle } from 'react';
import { MicIcon, MicOffIcon } from '../ui/icons';
import { S } from '../../theme';
import { useI18n } from '../../i18n/LanguageContext';
import {
  startListening,
  stopListening,
  useBrowserSpeech,
} from '../../lib/speech';
import {
  isWhisperSTTSupported,
  startWhisperRecording,
  stopWhisperRecording,
  pauseWhisperRecording,
  resumeWhisperRecording,
} from '../../lib/whisperSTT';

export interface VoiceRecorderHandle {
  start: () => void;
  stop: () => void;
  pause: () => void;
  resume: () => void;
}

interface VoiceRecorderProps {
  onTranscript?: (text: string) => void;
  onError?: (error: string) => void;
  onListeningChange?: (listening: boolean) => void;
  onInterim?: (text: string) => void;
}

const VoiceRecorder = forwardRef<VoiceRecorderHandle, VoiceRecorderProps>(function VoiceRecorder(
  { onTranscript, onError, onListeningChange, onInterim },
  ref,
) {
  const { lang } = useI18n();
  const [recording, setRecording] = useState(false);
  // macOS Safari: browser SpeechRecognition is non-functional → whisper bridge.
  const whisperMode = !useBrowserSpeech && isWhisperSTTSupported();
  const supported = useBrowserSpeech || whisperMode;
  const listeningRef = useRef(false);

  const setListening = useCallback(
    (value: boolean) => {
      listeningRef.current = value;
      setRecording(value);
      onListeningChange?.(value);
    },
    [onListeningChange],
  );

  const start = useCallback(() => {
    if (!supported || listeningRef.current) return;
    setListening(true);
    const handlers = {
      onTranscript: (text: string) => onTranscript?.(text),
      onEnd: () => setListening(false),
      onError: (err: string) => {
        if (err === 'not-allowed' || err === 'start_failed' || err === 'bridge_unreachable') {
          onError?.(err);
          setListening(false);
        }
      },
    };
    if (whisperMode) {
      startWhisperRecording(lang, handlers);
    } else {
      startListening(lang, {
        ...handlers,
        onInterim: (text) => onInterim?.(text),
      });
    }
  }, [supported, whisperMode, lang, onTranscript, onError, setListening, onInterim]);

  const stop = useCallback(() => {
    if (!listeningRef.current) return;
    if (whisperMode) {
      stopWhisperRecording();
    } else {
      stopListening();
    }
    setListening(false);
  }, [setListening, whisperMode]);

  // Ghost pause/resume used while Terra speaks: for the whisper backend we
  // stop capturing so Terra's own TTS is never transcribed back to Rasa.
  // Web Speech has its own end-of-speech ignore flag, so it's a no-op there.
  const pause = useCallback(() => {
    if (whisperMode) pauseWhisperRecording();
  }, [whisperMode]);

  const resume = useCallback(() => {
    if (whisperMode) resumeWhisperRecording();
  }, [whisperMode]);

  const toggle = useCallback(() => {
    if (listeningRef.current) {
      stop();
    } else {
      start();
    }
  }, [start, stop]);

  useImperativeHandle(ref, () => ({ start, stop, pause, resume }), [start, stop, pause, resume]);

  if (!supported) {
    return (
      <button
        disabled
        title="Speech recognition not supported"
        style={{
          width: 34, height: 34, flexShrink: 0,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          background: S.text3, border: 'none', color: '#0a0e17',
          cursor: 'not-allowed', borderRadius: 8,
        }}
      >
        <MicOffIcon style={{ width: 16, height: 16 }} />
      </button>
    );
  }

  return (
    <button
      onClick={toggle}
      style={{
        width: 34, height: 34, flexShrink: 0,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        background: recording ? '#ef4444' : S.solar,
        border: 'none', color: '#0a0e17',
        cursor: 'pointer',
        borderRadius: 8,
        transition: 'all 0.15s',
        position: 'relative',
      }}
      aria-label={recording ? 'Stop recording' : 'Start voice input'}
      aria-pressed={recording}
    >
      {recording ? (
        <>
          <MicOffIcon style={{ width: 16, height: 16 }} />
          <span style={{
            position: 'absolute', top: -4, right: -4,
            width: 10, height: 10, borderRadius: '50%',
            background: '#ef4444', border: '2px solid #0a0e17',
            animation: 'pulse 1s infinite',
          }} />
          <style>{`
            @keyframes pulse {
              0%, 100% { opacity: 1; transform: scale(1); }
              50% { opacity: 0.6; transform: scale(1.2); }
            }
          `}</style>
        </>
      ) : (
        <MicIcon style={{ width: 16, height: 16 }} />
      )}
    </button>
  );
});

export default VoiceRecorder;