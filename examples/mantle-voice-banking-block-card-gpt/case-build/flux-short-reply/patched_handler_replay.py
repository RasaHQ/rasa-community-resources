"""Replay the 54 saved Deepgram Flux sequences through Rasa 3.21.0.dev5's _DeepgramV2.parse_event,
unchanged and with one change: on EndOfTurn with an empty buffer, commit EndOfTurn's own transcript.
Offline: no key, no network. Input: flux-short-reply-frames.jsonl (messages after CloseStream excluded,
as in flux-short-reply-replay.txt)."""
import json, sys, hashlib, inspect, importlib.metadata as md
from collections import Counter
from rasa.core.channels.voice_stream.asr.deepgram.engine import _DeepgramV2
from rasa.core.channels.voice_stream.asr.deepgram.config import DeepgramV2ASRConfig
from rasa.core.channels.voice_stream.asr.asr_event import NewTranscript


class PatchedV2(_DeepgramV2):
    def parse_event(self, message):
        data = message if isinstance(message, dict) else json.loads(message)
        if (data.get("type") == "TurnInfo" and data.get("event") == "EndOfTurn"
                and not self._accumulated_transcript and data.get("transcript")):
            return NewTranscript(text=data["transcript"])
        return super().parse_event(message)


def run(cls, msgs):
    h = cls(DeepgramV2ASRConfig())
    outs = [h.parse_event(json.dumps(m["message"])) for m in msgs if not m["after_close_stream"]]
    commits = [o.text for o in outs if isinstance(o, NewTranscript)]
    return commits[-1] if commits else None, len(commits)


frames = sys.argv[1] if len(sys.argv) > 1 else "flux-short-reply-frames.jsonl"
lines = [json.loads(l) for l in open(frames) if l.strip()]
attempts = [l for l in lines if l.get("kind") == "attempt"]
src = inspect.getsource(_DeepgramV2.parse_event)
print("rasa-pro", md.version("rasa-pro"), "| _DeepgramV2.parse_event source sha256",
      hashlib.sha256(src.encode()).hexdigest()[:16], "| frames file", frames)
print("attempt | wav text | unchanged handler | patched handler | commits (unchanged/patched)")
tally = Counter()
for a in attempts:
    msgs = [l for l in lines if l.get("kind") == "message" and l["attempt"] == a["attempt"]]
    u, un = run(_DeepgramV2, msgs)
    p, pn = run(PatchedV2, msgs)
    tally[("unchanged", u is None)] += 1
    tally[("patched", p is None)] += 1
    tally["changed"] += (u != p)
    tally["double"] += (pn > 1)
    print(f"{a['attempt']:>2} | {a['text']:<22} | {u!r:<24} | {p!r:<24} | {un}/{pn}")
print()
print(f"attempts: {len(attempts)}")
print(f"unchanged handler returned None: {tally[('unchanged', True)]}")
print(f"patched handler returned None:   {tally[('patched', True)]}")
print(f"attempts whose committed text changed: {tally['changed']}")
print(f"attempts with more than one NewTranscript under the patch: {tally['double']}")
