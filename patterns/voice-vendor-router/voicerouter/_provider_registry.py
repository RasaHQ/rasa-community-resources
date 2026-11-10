"""Shared short-name aliases; explicit dotted provider paths do not use them."""

_PROVIDERS = {
    "asr": {"deepgram-shared": "deepgram.DeepgramASR", "speechmatics": "speechmatics.SpeechmaticsASR",
            "assemblyai": "assemblyai.AssemblyAIASR", "vosk": "vosk.VoskASR",
            "whisper": "whisper.FasterWhisperASR", "aws": "aws.TranscribeASR",
            "google": "google.GoogleSTT"},
    "tts": {"deepgram-shared": "deepgram.DeepgramTTS", "speechmatics": "speechmatics.SpeechmaticsTTS", "openai": "openai.OpenAITTS",
            "elevenlabs": "elevenlabs.ElevenLabsTTS", "rime-shared": "rime.RimeTTS", "aws": "aws.PollyTTS",
            "google": "google.GoogleTTS", "neutts": "neuphonic.NeuTTSLocal",
            "neutts-native": "neutts_native.NeuTTSNative"},
}
