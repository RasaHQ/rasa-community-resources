#!/usr/bin/env python3
"""Where the Rasa version's model calls go, by purpose, from a recorded run.

    python3 shared/spec/rasa_call_breakdown.py results/rasa/<run>            # table
    python3 shared/spec/rasa_call_breakdown.py results/rasa/<run> --json

Stdlib only. Two sources, depending on what the run recorded:

- ``call-purposes.jsonl`` (runs started through ``rasa_call_purposes.py``):
  one row per model call with the Mantle function that made it. Each row is
  matched to the meter's row for the same call (``llm-calls.jsonl``: same
  conversation window, nearest start time) for its price.
- Older runs without it: the LiteLLM log in ``raw/`` says which calls ran
  outside a turn (fact discovery, which Mantle runs after the reply), and the
  trackers in ``events/`` count rephrased messages (one rephrase call each);
  the rest are main-loop iterations. Less exact, and labelled as inferred.

Every call is also placed in a phase from the trackers: during a caller turn
the caller is waiting on, or after the hangup (Mantle runs one more turn on
``/session_end`` that nobody hears).
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path


def _rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()] if path.is_file() else []


def _session_end_times(run: Path) -> dict[str, float]:
    """conversation id -> timestamp of its /session_end user event."""
    report = json.loads((run / "results.json").read_text())
    out = {}
    for conv in report["conversations"]:
        events = json.loads((run / "events" / f"{conv['id']}.json").read_text()).get("events", [])
        ends = [e.get("timestamp") for e in events if e.get("event") == "user" and e.get("text") == "/session_end"]
        if ends:
            out[conv["conversation_id"]] = ends[-1]
    return out


def breakdown(run: Path) -> dict:
    meter = _rows(run / "llm-calls.jsonl")
    purposes = _rows(run / "call-purposes.jsonl")
    ends = _session_end_times(run)
    table: dict[tuple[str, str], dict] = defaultdict(lambda: {"calls": 0, "prompt_tokens": 0, "cost_usd": 0.0,
                                                              "ms": 0.0})
    tools_by_call: dict[str, int] = defaultdict(int)
    if purposes:
        source = "call-purposes.jsonl (labelled by Mantle function)"
        unmatched = list(meter)
        for row in purposes:
            match = min(unmatched, key=lambda m: abs(m["ts_start"] - row["ts_start"]), default=None)
            if match is not None and abs(match["ts_start"] - row["ts_start"]) < 1.0:
                unmatched.remove(match)
            end = ends.get(row.get("sender_id") or "")
            phase = "after hangup" if end is not None and row["ts_start"] >= end else "in a caller turn"
            cell = table[(row["purpose"], phase)]
            cell["calls"] += 1
            cell["prompt_tokens"] += row.get("prompt_tokens") or 0
            cell["cost_usd"] += (match or {}).get("cost_usd") or 0
            cell["ms"] += (row["ts_end"] - row["ts_start"]) * 1000
            if row["purpose"] == "orchestrator":
                key = "+".join(row["tool_calls"]) if row["tool_calls"] else ("text" if row["text_chars"] else "empty")
                tools_by_call[key] += 1
        notes = {"meter_rows_unmatched": len(unmatched)}
    else:
        source = "inferred: LiteLLM log (outside-turn calls) and tracker response sources"
        litellm = _rows(run / "raw" / "litellm-usage.jsonl")
        rephrased = 0
        for conv in json.loads((run / "results.json").read_text())["conversations"]:
            events = json.loads((run / "events" / f"{conv['id']}.json").read_text()).get("events", [])
            rephrased += sum((e.get("metadata") or {}).get("mantle_response_source") == "rephrased"
                             for e in events if e.get("event") == "bot")
        side = [r for r in litellm if r.get("sender_source") != "turn_context"]
        main = [r for r in litellm if r.get("sender_source") == "turn_context"]
        table[("fact_discovery", "any")] = {"calls": len(side), "prompt_tokens": sum(r["prompt_tokens"] for r in side),
                                            "cost_usd": sum(r["response_cost_usd"] or 0 for r in side),
                                            "ms": sum(r.get("latency_ms") or 0 for r in side)}
        table[("rephrase (one per rephrased message)", "any")] = {"calls": rephrased, "prompt_tokens": None,
                                                                 "cost_usd": None, "ms": None}
        table[("orchestrator and other in-turn calls", "any")] = {
            "calls": len(main) - rephrased, "prompt_tokens": None, "cost_usd": None, "ms": None}
        notes = {"in_turn_calls": len(main), "in_turn_prompt_tokens": sum(r["prompt_tokens"] for r in main),
                 "in_turn_cost_usd": round(sum(r["response_cost_usd"] or 0 for r in main), 6)}
    rows = [{"purpose": p, "phase": ph, **{k: (round(v, 4) if isinstance(v, float) else v) for k, v in c.items()}}
            for (p, ph), c in sorted(table.items(), key=lambda kv: -kv[1]["calls"])]
    return {"run": run.name, "source": source, "total_calls": len(meter), "rows": rows,
            "orchestrator_outcomes": dict(sorted(tools_by_call.items(), key=lambda kv: -kv[1])), **notes}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("run", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = breakdown(args.run.resolve())
    if args.json:
        print(json.dumps(report, indent=2))
        return 0
    print(f"{report['run']}: {report['total_calls']} model calls ({report['source']})")
    for r in report["rows"]:
        print(f"  {r['purpose']:<40} {r['phase']:<17} {r['calls']:>4} calls  tokens {r['prompt_tokens']}  "
              f"cost {r['cost_usd']}  model ms {r['ms']}")
    if report["orchestrator_outcomes"]:
        print("  orchestrator iterations by what the model returned:")
        for k, v in report["orchestrator_outcomes"].items():
            print(f"    {v:>4}  {k}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
