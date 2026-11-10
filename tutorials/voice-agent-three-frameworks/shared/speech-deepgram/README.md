# shared/speech-deepgram: Deepgram clients behind cedar_speech's interface

`cedar_speech_deepgram` gives the LangGraph and Strands versions Deepgram
speech for the comparison's Deepgram runs, without changing either folder.
It is a variant, not part of the shipped builds.

- `DeepgramASR`: Nova-3 streaming speech-to-text (`wss://api.deepgram.com/v1/listen`),
  one socket per call. Same methods as `cedar_speech.SpeechmaticsASR`:
  `open()`, `send_audio(pcm)`, `events()` yielding `cedar_speech.Transcript`,
  `close()`, `audio_seconds`.
- `DeepgramTTS`: Aura-2 text-to-speech over the `/v1/speak` socket
  (`aura-2-thalia-en`, linear16 at 24 kHz). Same methods as
  `cedar_speech.SpeechmaticsTTS`: `synthesize(text) -> PCM`, `close()`.
- `launch.py`: starts a version's own `server.py` with these two classes
  under the Speechmatics names, so the voice loop runs unchanged:

```bash
cd langgraph && uv run --locked python ../shared/speech-deepgram/launch.py server.py --port 5006
make spec-deepgram FW=langgraph LABEL=<run>        # from the tutorial folder (billed)
```

The settings are the defaults of Rasa 3.21.0.dev5's built-in Deepgram
engines: endpointing 400 ms, `utterance_end_ms` 1000, `smart_format`,
interim results, no keyterms (Rasa's engine has no field for them). Final
results are held until `speech_final` or `UtteranceEnd` and sent as one
transcript, as Rasa's engine does. `../../rasa/tests/test_speech_parity.py`
builds Rasa's engines from `../../variants/rasa-deepgram.integrations.yml`
and checks the query parameters and the turn joining against this package.

It needs `DEEPGRAM_API_KEY` (the repository-root `.env` is loaded by the
spec runner). Offline tests, using `cedar_speech`'s environment for
`websockets`:

```bash
cd ../speech && uv run --python 3.12 python -m unittest discover -s ../speech-deepgram/tests -v
```

Counted by the plan's rule (`python3 shared/spec/count_concerns.py shared/speech-deepgram`):
184 lines of voice-adapter code and 13 of ops (the launcher). The voice
loops do not take streaming text: they still call `synthesize()` once per
sentence, as they do with Speechmatics.
