# shared/speech: Speechmatics clients for the LangGraph and Strands servers

`cedar_speech` is the voice adapter for the two versions that have no speech
engines of their own: Speechmatics realtime speech-to-text over a WebSocket,
and Speechmatics text-to-speech over HTTP. No framework imports.

The Rasa version reaches the same vendor through its own custom engine
classes ([`../../rasa/engines/speechmatics.py`](../../rasa/engines/speechmatics.py),
a copy of the companion's live-tested
`voicerouter.providers.speechmatics` adapters). This package sends the same
messages with the same settings; `rasa/tests/test_speech_parity.py` compares
the two message for message. So all three versions make identical vendor
calls, and the vendor-adapter line of the comparison is roughly equal.

```bash
uv run --python 3.12 python -m unittest tests.test_offline -v   # no network
uv run --python 3.12 python -m unittest tests.test_live -v      # billed: a few seconds of realtime audio
```

The live test needs `SPEECHMATICS_API_KEY`, from the environment or the
repository's `.env` (loaded the way the companion's tooling loads it, never
printed).

## What is used

| | Endpoint | Settings |
|---|---|---|
| Speech-to-text | `wss://eu.rt.speechmatics.com/v2` (realtime, EU) | `language: en`, `operating_point: enhanced`, `max_delay: 1.0`, partials on, `end_of_utterance_silence_trigger: 0.7`, `additional_vocab`: the clinic's medicine names. Raw `pcm_s16le` at 24 kHz |
| Text-to-speech | `https://preview.tts.speechmatics.com/generate/megan?output_format=wav_16000` | Voice `megan`; the API accepts only `wav_16000` or `pcm_16000` (anything else is HTTP 422, checked 2026-09-30). The 16 kHz WAV is resampled to 24 kHz |

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

## What it does not do

It is the vendor client only. The voice loop is yours to write, and it is
what the comparison counts as voice-loop code: the browser_audio server
([`../web/PROTOCOL.md`](../web/PROTOCOL.md)), passing audio to the ASR,
starting an agent turn on each final transcript, splitting replies into
sentences for TTS if you want the first sentence to play sooner, sending
audio with playback markers and latency, and whatever you do about barge-in,
silence and fillers while a tool runs.

## Known behaviour (from the companion's builds)

- **Speechmatics finalises a word or two at a time.** Without an
  end-of-utterance trigger, one 14-second caller turn reached the Northgate
  dispute build's agent as 19 user turns. With the 0.7 s trigger the
  segments are held and sent as one final transcript. Keep it.
- **The socket must be configured first.** `StartRecognition` is the first
  message; audio sent before it is never transcribed, with no error.
- **Numbers come back as digits.** "March fourteenth, nineteen sixty-eight"
  was transcribed as "March 14th, 1968" in the live test.
- **Names need help.** In the dispute build a seven-entry custom vocabulary
  took name-dependent calls from 6 of 11 passes to 11 of 11. Here the
  vocabulary holds only the medicine names, which the clinic knows in
  advance; patient names are not in it.
- **Billing.** Realtime is billed per second streamed, and a browser streams
  continuously, silence included. TTS is documented as "currently in preview
  and free to use" (docs.speechmatics.com, read 2026-09-30); no per-character
  price was published.
