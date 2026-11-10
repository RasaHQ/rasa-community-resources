# shared/speech: Speechmatics clients for the tutorial servers

`cedar_speech` provides Speechmatics realtime speech-to-text over a
WebSocket and text-to-speech over HTTP. It has no framework imports. The
non-Rasa tutorial servers use these clients behind the shared browser protocol.

Rasa uses custom engine classes in
[`../../rasa/engines/speechmatics.py`](../../rasa/engines/speechmatics.py).
`rasa/tests/test_speech_parity.py` checks that those engines and this package
construct the same configured provider messages.

```bash
uv run --python 3.12 python -m unittest tests.test_offline -v   # no network
uv run --python 3.12 python -m unittest tests.test_live -v      # billed: a few seconds of realtime audio
```

The live test needs an authorized `SPEECHMATICS_API_KEY` in the environment.
It makes paid provider calls; do not include credentials in test output.

## What is used

| | Endpoint | Settings |
|---|---|---|
| Speech-to-text | `wss://eu.rt.speechmatics.com/v2` (realtime, EU) | `language: en`, `operating_point: enhanced`, `max_delay: 1.0`, partials on, `end_of_utterance_silence_trigger: 0.7`, `additional_vocab`: the clinic's medicine names. Raw `pcm_s16le` at 24 kHz |
| Text-to-speech | `https://preview.tts.speechmatics.com/generate/megan?output_format=wav_16000` | Voice `megan`, requesting `wav_16000`; the 16 kHz WAV is resampled to 24 kHz |

All of it is in [`cedar_speech/config.py`](cedar_speech/config.py).

## Interface

```python
from cedar_speech import SpeechmaticsASR, SpeechmaticsTTS

# One ASR socket per call.
async with SpeechmaticsASR() as asr:              # connects, sends StartRecognition
    await asr.send_audio(pcm_20ms)                # for every {"audio"} frame from the browser
    async for event in asr.events():              # Transcript(text, final, at)
        if event.final:                           # one per caller turn, at EndOfUtterance
            ...                                   # run the agent turn
        else:
            ...                                   # the caller is speaking (partial)
# on exit: EndOfStream with last_seq_no, then close. asr.audio_seconds = seconds streamed (billed).

# One TTS client per process.
tts = SpeechmaticsTTS()
pcm = await tts.synthesize("Your request reference is R Q, two three six seven.")   # 24 kHz PCM16
tts.last_timings   # {"chars", "headers_s", "total_s", "audio_s"}
await tts.close()
```

`cedar_speech.protocol` has the wire messages as pure functions
(`start_recognition`, `end_of_stream`, `ReplyReader`, `tts_request`), and
`cedar_speech.audio` the PCM helpers (`wav_to_pcm`, `b64_pcm`, `frames`).

## Voice-loop responsibilities

The server handles the [`browser_audio` protocol](../web/PROTOCOL.md):
audio frames, agent turns, sentence chunking, playback markers and the events
endpoint. This package handles provider communication and audio conversion.

## Configuration and usage

- Collect final recognition segments until the end-of-utterance event.
- Handle numeric and spoken forms of dates in application validation.
- Supply only vocabulary known before a call. The clinic medicine names are
  configured; caller names are not supplied as recognition hints.
- Continuous audio includes silence. Check the provider's current pricing
  and account terms before running live tests.

## Select a shared vendor router

All eight tutorial implementations accept `CEDAR_VOICE_ROUTER_CONFIG`, an absolute
path to a versioned JSON profile. The example is
[`profiles/speechmatics-fixed.json`](profiles/speechmatics-fixed.json).
`create_asr()` and `create_tts()` in `cedar_speech.router` adapt the shared router
back to this package's PCM/transcript interface. Rasa's existing custom engine
factories select the same router when the variable is set.

Provider credentials remain environment variables. Do not store them in profiles.
An invalid profile fails before a connection is opened. With no profile selected,
the original Speechmatics clients and settings remain the defaults. Shared provider
implementation and installation details are in
[the router README](../../../../patterns/voice-vendor-router/README.md).
