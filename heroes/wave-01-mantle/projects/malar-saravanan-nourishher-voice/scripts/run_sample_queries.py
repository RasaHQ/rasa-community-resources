#!/usr/bin/env python3
"""Send demo queries to a running Rasa REST server and print replies.

Requires the API server: ``uv run rasa run --enable-api --port 5011`` (or ``make api``).
Not part of the automated eval harness — use ``make test`` / ``make e2e`` for that.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import httpx

API = "http://localhost:5011/webhooks/rest/webhook"
SENDER = "sample-queries-run"
TIMEOUT = 180.0

QUERIES = [
    ("1 intro", "hi"),
    ("2 intake", "My name is Aya and I want steadier energy through the day"),
    (
        "6 meal log",
        "I had two idlis with sambar and a coffee for breakfast",
    ),
    (
        "7 USDA nutrition",
        "how much protein and iron is in 100 grams of chana dal?",
    ),
]


def send(client: httpx.Client, message: str) -> list[str]:
    r = client.post(
        API,
        json={"sender": SENDER, "message": message},
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    payloads = r.json()
    texts: list[str] = []
    for item in payloads:
        if isinstance(item, dict) and item.get("text"):
            texts.append(str(item["text"]).strip())
    return texts


def main() -> int:
    data_dir = Path.cwd() / "data"
    print(f"REST endpoint: {API}")
    print(f"sender id: {SENDER}\n")

    with httpx.Client() as client:
        for label, message in QUERIES:
            print("=" * 72)
            print(f"[{label}] USER: {message}")
            try:
                t0 = time.perf_counter()
                texts = send(client, message)
                elapsed = time.perf_counter() - t0
            except Exception as exc:
                print(f"  ERROR: {exc}")
                return 1

            if not texts:
                print("  BOT: (empty — no text in response)")
            else:
                for i, text in enumerate(texts, 1):
                    head = text[:500] + ("…" if len(text) > 500 else "")
                    print(f"  BOT[{i}] ({elapsed:.1f}s): {head}")
            print()

    print("=" * 72)
    print("data/ after run:")
    if not data_dir.exists():
        print("  (no data/ directory)")
        return 0
    files = sorted(data_dir.rglob("*"))
    runtime = [p for p in files if p.is_file() and p.name != ".gitignore"]
    if not runtime:
        print("  (no runtime files yet — only .gitignore)")
    else:
        for p in runtime:
            print(f"  {p.relative_to(data_dir)}  ({p.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
