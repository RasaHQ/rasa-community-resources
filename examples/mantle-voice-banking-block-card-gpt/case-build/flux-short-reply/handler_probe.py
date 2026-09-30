"""Feed Deepgram Flux (/v2/listen) TurnInfo frames to Rasa's own handler and print what it returns.
Frames are hand-built, not recorded from Deepgram: they show the handler's behaviour, not Flux's."""
import json, importlib.metadata as m
from rasa.core.channels.voice_stream.asr.deepgram.engine import _DeepgramV2
from rasa.core.channels.voice_stream.asr.deepgram.config import DeepgramV2ASRConfig
print("rasa-pro", m.version("rasa-pro"))
def frame(event, transcript):
    return json.dumps({"type": "TurnInfo", "event": event, "transcript": transcript})
def run(name, frames):
    h = _DeepgramV2(DeepgramV2ASRConfig())
    print("\n==", name)
    for ev, tr in frames:
        out = h.parse_event(frame(ev, tr))
        print(f"  {ev:12s} transcript={tr!r:8s} -> {out!r}")
run("StartOfTurn, Update, EndOfTurn (the path the build heard 6 of 10 'Yes.')",
    [("StartOfTurn", ""), ("Update", "Yes"), ("EndOfTurn", "Yes.")])
run("StartOfTurn, EndOfTurn carrying the transcript, no Update",
    [("StartOfTurn", ""), ("EndOfTurn", "Yes.")])
run("EndOfTurn with transcript, no StartOfTurn, no Update",
    [("EndOfTurn", "Yes.")])
