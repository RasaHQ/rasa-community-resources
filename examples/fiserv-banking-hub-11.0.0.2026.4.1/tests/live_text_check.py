"""Manual end-to-end text check through the REST channel. NOT part of `make test`.

It starts the example (`run_demo.py --text-api`), sends the README conversation as
text and checks the answers. It needs the Fiserv release ZIP in vendor-inputs/ and the three
Codespaces secrets, and it makes real model calls (a few cents). Run it only on
purpose:  uv run --locked python tests/live_text_check.py
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
PORT = 5006
URL = f"http://127.0.0.1:{PORT}/webhooks/rest/webhook"

CHECKS = [  # (sender, message, all of these substrings, none of these)
    ("a", "What accounts do I have?", ["DDA", "SDA", "LOAN"], ["checking", "savings"]),
    ("a", "What is the balance of DDA-A?", ["not available"], ["$", "USD"]),
    ("a", "What did I spend recently on DDA-A?", ["not available"], ["USD"]),
    ("a", "When is my next loan payment on LOAN-A?", ["December 1", "not available"], ["$", "USD"]),
    ("a", "What is my payoff on LOAN-A?", ["not available"], ["$", "USD"]),
    ("a", "What is the balance of DDA-B?", [], ["available balance is"]),
    ("b", "Move 5 dollars from DDA-A to SDA-A.", ["not available"], ["confirm transfer", "accepted"]),
    ("b", "Confirm transfer.", [], ["accepted"]),
]


def say(sender, message):
    request = urllib.request.Request(URL, json.dumps({"sender": sender, "message": message}).encode(),
                                     {"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=120) as reply:
        return " | ".join(item.get("text", "") for item in json.load(reply))


def main():
    process = subprocess.Popen([sys.executable, "run_demo.py", "--text-api", "--port", str(PORT)], cwd=ROOT,
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=dict(os.environ))
    try:
        deadline = time.time() + 180
        for line in process.stdout:
            if "up and running" in line:
                break
            if "Not ready" in line or time.time() > deadline:
                print(line.strip())
                return 2
        failures = 0
        for sender, message, needed, banned in CHECKS:
            answer = say(sender, message)
            problems = [f"missing {text!r}" for text in needed if text.lower() not in answer.lower()]
            problems += [f"unexpected {text!r}" for text in banned if text.lower() in answer.lower()]
            print(("FAIL " if problems else "ok   ") + message + ("  -> " + "; ".join(problems) if problems else ""))
            print("     reply: " + answer)  # keep the exact reply as evidence
            failures += bool(problems)
        print(f"{len(CHECKS) - failures}/{len(CHECKS)} checks passed")
        return 1 if failures else 0
    finally:
        process.terminate()
        try:
            process.wait(timeout=20)
        except subprocess.TimeoutExpired:
            process.kill()


if __name__ == "__main__":
    raise SystemExit(main())
