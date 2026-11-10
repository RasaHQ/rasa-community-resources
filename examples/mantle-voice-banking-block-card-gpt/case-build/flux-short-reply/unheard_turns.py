"""Fail a voice run if a spoken caller turn produced no user event."""
import json
import sys

SILENCE_TIMEOUT_MS = 30_000  # integrations.yml: silence_timeout: 30


def unheard_turns(path):
    run = json.load(open(path))
    for call in run["conversations"]:
        for i, turn in enumerate(call["turns"]):
            extra = turn.get("extra") or {}
            if extra.get("mode") != "audio":
                continue
            events = len(extra.get("heard") or [])  # new user events in the tracker
            wait = turn.get("latency_ms") or 0
            if events == 0 or wait >= SILENCE_TIMEOUT_MS:
                yield call["id"], i, turn["user"], events, wait


found = [row for path in sys.argv[1:] for row in unheard_turns(path)]
for call_id, i, said, events, wait in found:
    print(f"{call_id} turn {i}: said {said!r}, user events {events}, wait {wait:,.0f} ms")
print(f"{len(found)} unheard turn(s)")
sys.exit(1 if found else 0)
