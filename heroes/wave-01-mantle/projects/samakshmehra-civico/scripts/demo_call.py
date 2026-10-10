#!/usr/bin/env python3
"""Drive a running agent from the terminal. Needs `make run` in another shell.

    uv run python scripts/demo_call.py report
    uv run python scripts/demo_call.py status
    uv run python scripts/demo_call.py "one line to say"
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.request

URL = os.getenv("CIVICO_REST_URL", "http://localhost:5007/webhooks/rest/webhook")

SCRIPTS = {
    "gate": [
        "I want to report a street light not working outside Juniper Heights main gate in Vasundhara. My number is 9000000005.",
        "Actually, the other gate",
        "Yes, please submit the corrected report",
    ],
    "natural": [
        "I want to file a complaint",
        "It is nearby my society only",
        "Near Juniper Heights, Vashali, Ghaziabad",
        "The light bulb is not working",
        "It is near the metro station, Vikas Marg",
        "9000000000",
        "Yes, please file it",
    ],
    "quick": [
        "I want to report garbage bags left for three days outside the Juniper School gate in Indirapuram. Use 9000000001 as my callback number.",
        "Yes, please file it",
    ],
    "revise": [
        "I want to report a street light not working outside Juniper School in Vasundhara. My number is 9000000002.",
        "No, change the spot to the park gate opposite the school",
        "Yes, please file the corrected complaint",
    ],
    "join": [
        "I want to report an overflowing drain outside the corner shop on the main road in Vaishali. My number is 9000000003.",
        "It is the same issue",
        "Yes, add my report",
    ],
    "cancel": [
        "I want to report no water supply at Juniper Heights in Vasundhara. My callback number is 9000000004.",
        "No, cancel the complaint. I do not want to submit anything.",
    ],
    "status": [
        "What happened to my complaint C I V one zero zero two?",
        "Yes please raise it",
        "Yes go ahead",
    ],
    "who": ["Who handles garbage in Indirapuram?", "No thanks, not right now"],
    "scope": ["My property tax bill is wrong"],
}


SCRIPTS["report"] = SCRIPTS["quick"]
SCRIPTS["duplicate"] = SCRIPTS["join"]
SCRIPTS["correction"] = SCRIPTS["revise"]


def say(sender: str, message: str) -> tuple[list[str], float]:
    body = json.dumps({"sender": sender, "message": message}).encode()
    request = urllib.request.Request(
        URL, data=body, headers={"Content-Type": "application/json"})
    started = time.time()
    with urllib.request.urlopen(request, timeout=300) as response:
        payload = json.load(response)
    return [item["text"] for item in payload if item.get("text")], time.time() - started


def main() -> None:
    arg = sys.argv[1] if len(sys.argv) > 1 else "report"
    lines = SCRIPTS.get(arg, [arg])
    sender = f"demo-{arg}-{int(time.time())}"
    print(f"Conversation: {sender}", flush=True)

    # On a real call the agent speaks first — the caller picking up is not a
    # message. Over REST there is no "pick up", so the first thing sent is what
    # triggers the session-start greeting and is otherwise discarded. Prime it,
    # or the first scripted line disappears into the greeting.
    greeting, _ = say(sender, "hello")
    for text in greeting:
        print(f"\033[36mBOT \033[0m {text}")

    for line in lines:
        replies, took = say(sender, line)
        print(f"\n\033[2mYOU \033[0m {line}")
        for reply in replies:
            print(f"\033[36mBOT \033[0m {reply}")
        print(f"\033[2m      {took:.1f}s\033[0m")
        # Fresh seeds and previous rehearsals may produce different matches.
        # These new-report scripts explicitly mean a different incident;
        # the join script supplies its own same-incident answer.
        if arg not in {"join", "duplicate"} and any(
                "same issue" in reply.lower() and "different" in reply.lower()
                for reply in replies):
            answer = "It is a different incident. Keep this as a new report."
            extra, _ = say(sender, answer)
            print(f"\nYOU   {answer}")
            for reply in extra:
                print(f"BOT   {reply}")
    print()


if __name__ == "__main__":
    main()
