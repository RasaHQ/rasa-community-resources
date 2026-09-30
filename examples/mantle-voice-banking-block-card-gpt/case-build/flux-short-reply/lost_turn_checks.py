"""For every caller turn that produced no user event, list the conversation's failed checks.
Reads committed results.json files only."""
import json, sys

for path in sys.argv[1:]:
    run = json.load(open(path))
    for conv in run["conversations"]:
        lost = [i for i, t in enumerate(conv["turns"])
                if t.get("extra", {}).get("mode") == "audio" and not t.get("extra", {}).get("heard")]  # no new user event, as in unheard_turns.py
        if not lost:
            continue
        print(f"{path.split('/')[0]} {conv['id']} turn(s) {lost} (0-based, as unheard_turns.py prints) passed={conv['passed']}")
        for c in conv["checks"]:
            if not c["passed"]:
                chk = c["check"]
                print(f"  FAILED {chk['type']} {chk.get('tool')}: {c['detail']}")
