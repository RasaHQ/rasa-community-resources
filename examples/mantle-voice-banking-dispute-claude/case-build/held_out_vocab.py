#!/usr/bin/env python3
"""Held-out vocabulary: per-call outcomes, checked tokens by kind and false positives. Stdlib only, no spend.

    python3 case-build/held_out_vocab.py

The ledger's six merchants split in two by transaction id
(lib/fixtures/northgate_disputes.json): Brightmart Online (NB-TXN-3101),
Lakeview Fuel (3102) and Hollins Fitness (3104) are held out; Saffron Table
(3105), Metro Cabs (3106) and Cinnabar Streaming (3107) are the vocabulary
(the `held-out-vocab` variant in case-build/conversations.json). The
surname is in neither half: no run here lists it, so it is reported on its
own row. The calls are the 11 whose checked merchant tokens are all in the
held-out half, the same 11 as the 2026-09-29 custom-vocab run.

Reads four runs of those 11 calls, when present:

- 2026-09-29-claude-sonnet-5.5 (no vocabulary; the main run, filtered to the 11)
- 2026-09-29-custom-vocab (all six merchants and the surname)
- 2026-10-02-held-out-vocab (the three vocabulary merchants only)
- 2026-10-02-held-out-control (no vocabulary, same day)

For each: pass or fail per call, the checked speech-to-text tokens by kind
(name tokens split into held-out merchant, surname and first name), and
false positives: a vocabulary entry, or one word of a multi-word entry, in
what speech-to-text produced for a turn whose script does not contain it.
Writes held-out-vocab.json next to this script and prints the tables.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"
SPEC = json.loads((HERE / "conversations.json").read_text())

HELD_OUT = ("Brightmart", "Lakeview", "Hollins")
SURNAME = "Raghunathan"
FIRST_NAMES = ("Priya", "Arjun")
CALLS = (
    "normal-brightmart-unrecognised", "normal-date-said-numerically", "normal-second-customer-arjun",
    "normal-dispute-and-block-card", "adversarial-refund-now", "adversarial-ambiguous-file-both",
    "adversarial-skip-confirmation", "recovery-ambiguous-then-amount", "correction-recognises-gym",
    "correction-self-corrected-amount", "short-reply-yes",
)
RUNS = (
    ("2026-09-29-claude-sonnet-5.5", "no vocabulary (2026-09-29 main run)"),
    ("2026-09-29-custom-vocab", "all six merchants + surname (2026-09-29)"),
    ("2026-10-02-held-out-vocab", "held-out: Saffron Table, Metro Cabs, Cinnabar Streaming"),
    ("2026-10-02-held-out-control", "no vocabulary (2026-10-02 control)"),
)


def vocabulary(variant: str | None) -> list[str]:
    """The `content` of each additional_vocab entry the variant adds to integrations.yml."""
    if not variant:
        return []
    text = "".join(e["replace"] for e in SPEC["variants"][variant]["edits"])
    return re.findall(r"- content: (.+)", text)


def kind_of(token: dict) -> str:
    if token["kind"] != "name":
        return token["kind"]
    if token["token"] in HELD_OUT:
        return "name: held-out merchant"
    if token["token"] == SURNAME:
        return "name: surname"
    if token["token"] in FIRST_NAMES:
        return "name: first name"
    return "name: other"


def has(text: str, phrase: str) -> bool:
    return re.search(rf"\b{re.escape(phrase)}\b", text, re.I) is not None


def false_positives(conv: dict, vocab: list[str]) -> list[dict]:
    found = []
    for turn in (conv.get("voice") or {}).get("asr") or []:
        heard = " ".join(turn.get("heard") or [])
        for entry in vocab:
            for piece in {entry, *entry.split()}:
                if len(piece) >= 4 and has(heard, piece) and not has(turn["intended"], piece):
                    found.append({"call": conv["id"], "entry": entry, "matched": piece,
                                  "intended": turn["intended"], "heard": heard})
    return found


def analyse(label: str, title: str) -> dict | None:
    path = RESULTS / label / "results.json"
    if not path.is_file():
        return None
    report = json.loads(path.read_text())
    variant = (report.get("variant") or {}).get("name")
    vocab = vocabulary(variant)
    convs = [c for c in report["conversations"] if c["id"] in CALLS]
    kinds: dict[str, dict] = {}
    misses = []
    for conv in convs:
        for turn in (conv.get("voice") or {}).get("asr") or []:
            for token in turn.get("tokens") or []:
                k = kinds.setdefault(kind_of(token), {"checked": 0, "exact": 0, "normalised": 0})
                k["checked"] += 1
                k["exact"] += bool(token["exact"])
                k["normalised"] += bool(token["normalised"])
                if token["kind"] == "name" and not token["exact"]:
                    misses.append({"call": conv["id"], "token": token["token"], "heard": " ".join(turn["heard"])})
    return {
        "run": label,
        "condition": title,
        "variant": variant,
        "vocabulary": vocab,
        "calls": {c["id"]: c["outcome"] for c in convs},
        "passed": sum(c["outcome"] == "pass" for c in convs),
        "of": len(convs),
        "tokens": dict(sorted(kinds.items())),
        "name_misses": misses,
        "false_positives": [fp for c in convs for fp in false_positives(c, vocab)],
        "cost_usd": round(sum((c["usage"]["cost_usd"] or 0) + ((c.get("voice") or {}).get("cost_usd") or 0)
                              for c in convs), 6),
    }


def main() -> int:
    runs = [r for r in (analyse(label, title) for label, title in RUNS) if r]
    by = {r["run"]: r for r in runs}
    flips = []
    a, b = by.get("2026-10-02-held-out-vocab"), by.get("2026-10-02-held-out-control")
    if a and b:
        flips = [{"call": cid, "held_out_vocab": a["calls"].get(cid), "control": b["calls"].get(cid)}
                 for cid in CALLS if a["calls"].get(cid) != b["calls"].get(cid)]
    report = {"held_out": list(HELD_OUT), "surname": SURNAME, "calls": list(CALLS), "runs": runs,
              "flips_held_out_vs_control": flips}
    (HERE / "held-out-vocab.json").write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n")

    print("| call | " + " | ".join(r["run"] for r in runs) + " |")
    print("|---|" + "---|" * len(runs))
    for cid in CALLS:
        print(f"| {cid} | " + " | ".join(r["calls"].get(cid, "-") for r in runs) + " |")
    print("| passed | " + " | ".join(f"{r['passed']}/{r['of']}" for r in runs) + " |")
    kinds = sorted({k for r in runs for k in r["tokens"]})
    print()
    print("| kind (exact / normalised / checked) | " + " | ".join(r["run"] for r in runs) + " |")
    print("|---|" + "---|" * len(runs))
    for k in kinds:
        cells = []
        for r in runs:
            t = r["tokens"].get(k)
            cells.append(f"{t['exact']} / {t['normalised']} / {t['checked']}" if t else "-")
        print(f"| {k} | " + " | ".join(cells) + " |")
    print()
    for r in runs:
        print(f"{r['run']}: vocabulary {r['vocabulary'] or 'none'}; false positives {len(r['false_positives'])}; "
              f"cost {r['cost_usd']} USD")
    print("flips (held-out vocab vs control):", flips or "none")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
