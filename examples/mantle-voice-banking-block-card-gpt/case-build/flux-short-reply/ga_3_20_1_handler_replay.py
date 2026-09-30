"""Replay the 54 saved Deepgram Flux sequences through the _DeepgramV2 handler from the released
rasa-pro 3.20.1 wheel, loaded from that wheel's engine.py into the 3.21.0.dev5 environment
(the two engine.py files differ in one line, StartOfTurn's return value; see ga-3-20-1-handler-check.txt).
Offline: no key, no network."""
import json, sys, zipfile, hashlib, importlib.util, types
from collections import Counter

wheel, frames = sys.argv[1], sys.argv[2]
src = zipfile.ZipFile(wheel).read("rasa/core/channels/voice_stream/asr/deepgram/engine.py")
print("wheel", wheel.split("/")[-1], "sha256", hashlib.sha256(open(wheel, "rb").read()).hexdigest())
print("engine.py sha256", hashlib.sha256(src).hexdigest())
mod = types.ModuleType("rasa.core.channels.voice_stream.asr.deepgram.engine_3_20_1")
mod.__package__ = "rasa.core.channels.voice_stream.asr.deepgram"
exec(compile(src, "rasa-pro-3.20.1/engine.py", "exec"), mod.__dict__)
from rasa.core.channels.voice_stream.asr.deepgram.config import DeepgramV2ASRConfig

lines = [json.loads(l) for l in open(frames) if l.strip()]
attempts = [l for l in lines if l.get("kind") == "attempt"]
tally = Counter()
print("attempt | wav text | 3.20.1 handler outputs (before CloseStream) | committed")
for a in attempts:
    h = mod._DeepgramV2(DeepgramV2ASRConfig())
    msgs = [l for l in lines if l.get("kind") == "message" and l["attempt"] == a["attempt"] and not l["after_close_stream"]]
    outs = [o for o in (h.parse_event(json.dumps(m["message"])) for m in msgs) if o is not None]
    commits = [o.text for o in outs if type(o).__name__ == "NewTranscript"]
    final = commits[-1] if commits else None
    tally[final is None] += 1
    shown = ", ".join(f"{type(o).__name__}({o.text!r})" for o in outs)
    print(f"{a['attempt']:>2} | {a['text']:<22} | {shown[:90]:<90} | {final!r}")
print()
print(f"attempts: {len(attempts)}; 3.20.1 handler committed nothing: {tally[True]}")
