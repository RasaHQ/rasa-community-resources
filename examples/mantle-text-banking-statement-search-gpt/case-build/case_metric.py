#!/usr/bin/env python3
"""The case metric and receipt delivery for a recorded run, from its trackers. Stdlib only, no spend.

    python3 case-build/case_metric.py case-build/results/<label>

Metric (casebook): incomplete result sets presented as complete, divided by
search responses.

- Search responses: search_transactions and continue_search results that
  issued a result (status complete or partial), in every conversation.
- Presented as complete: while the latest issued search in the conversation
  was partial, a bot message the customer saw (not a verbatim response, not
  the tool's own receipt) had a sentence that presents a result set as
  complete (lib.history.complete_claims: a period total, "that's all", "the
  full list", "you spent $X"). Counted per partial result.

Also: search totals called a statement balance (lib.history.statement_claims,
against the totals of complete searches the conversation had seen).

Receipt delivery: the case's receipt is a search reference with the time
range, the included statuses and whether the result is complete. For every
issued result, did a bot message in the same customer turn carry the
reference, and who wrote it: the tool (its own receipt, TOOL_SENDS_RECEIPT)
or the model. Turns where the model added no text of its own after an
issued result are listed as silent completions.

Each counted item is listed with its conversation, so every count can be
checked against the tracker by hand. Writes case-metric.json next to the
trackers.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

from lib import history as nb  # noqa: E402

SEARCH_TOOLS = ("search_transactions", "continue_search")


def _result(raw):
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except ValueError:
            return {}
    return raw if isinstance(raw, dict) else {}


def _is_tool_receipt(events: list[dict], i: int) -> bool:
    """Whether bot event i is the receipt text the next tool result produced (it is recorded just before)."""
    text = events[i].get("text") or ""
    for e in events[i + 1:]:
        kind = e.get("event")
        if kind == "tool_executed":
            return nb.customer_receipt(e.get("tool_name"), _result(e.get("result"))) == text
        if kind in ("user", "bot"):
            return False
    return False


def scan(name: str, tracker: dict) -> dict:
    events = [e for e in tracker.get("events", []) if e.get("event") in ("user", "bot", "tool_executed")]
    turn = -1
    for e in events:
        if e["event"] == "user":
            turn += 1
        e["_turn"] = turn
    report = {"responses": 0, "partial_responses": 0, "complete_responses": 0, "presented_as_complete": [],
              "statement_claims": [], "receipts": [], "silent_completions": [], "tool_receipt_messages": 0}
    searches: dict[str, dict] = {}
    latest: str | None = None
    flagged: set[tuple[str, int]] = set()
    receipt_idx = {i for i, e in enumerate(events) if e["event"] == "bot" and _is_tool_receipt(events, i)}
    report["tool_receipt_messages"] = len(receipt_idx)
    issued = []
    for i, e in enumerate(events):
        if e["event"] == "tool_executed" and e.get("tool_name") in SEARCH_TOOLS:
            value = _result(e.get("result"))
            if value.get("status") not in ("complete", "partial"):
                continue
            report["responses"] += 1
            report[f"{value['status']}_responses"] += 1
            ref = value["search_ref"]
            searches[ref] = value
            latest = ref
            issued.append((i, value))
        elif e["event"] == "bot" and i not in receipt_idx:
            if (e.get("metadata") or {}).get("mantle_response_source") == "verbatim":
                continue
            text = e.get("text") or ""
            if latest and not searches[latest]["complete"]:
                claims = nb.complete_claims(text)
                key = (latest, searches[latest]["count"])
                if claims and key not in flagged:
                    flagged.add(key)
                    report["presented_as_complete"].append(
                        {"conversation": name, "search_ref": latest, "count_read": searches[latest]["count"],
                         "matched": claims, "text": text})
            totals = [t for s in searches.values() if s["complete"]
                      for t in (s.get("total_debits"), s.get("total_credits")) if t and t != "$0.00"]
            for sentence in nb.statement_claims(text, totals):
                report["statement_claims"].append({"conversation": name, "sentence": sentence})
    for i, value in issued:
        turn_ = events[i]["_turn"]
        ref = value["search_ref"]
        same_turn = [(j, b) for j, b in enumerate(events) if b["event"] == "bot" and b["_turn"] == turn_]
        by_tool = any(j in receipt_idx and ref in (b.get("text") or "") for j, b in same_turn)
        by_model = any(j not in receipt_idx and ref in (b.get("text") or "") for j, b in same_turn)
        model_after = [b for j, b in same_turn if j > i and j not in receipt_idx
                       and (b.get("metadata") or {}).get("mantle_response_source") != "verbatim"]
        report["receipts"].append({"conversation": name, "search_ref": ref, "status": value["status"],
                                   "delivered_same_turn": by_tool or by_model, "by_tool_receipt": by_tool,
                                   "ref_in_model_text": by_model})
        if not model_after:
            report["silent_completions"].append({"conversation": name, "search_ref": ref, "turn": turn_})
    return report


def main() -> int:
    run = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if run is None or not (run / "trackers").is_dir():
        print(__doc__)
        return 2
    total = {"run": run.name, "conversations": 0, "responses": 0, "partial_responses": 0, "complete_responses": 0,
             "presented_as_complete": [], "statement_claims": [], "receipts": [], "silent_completions": [],
             "tool_receipt_messages": 0}
    for path in sorted((run / "trackers").glob("*.json")):
        one = scan(path.stem, json.loads(path.read_text()))
        total["conversations"] += 1
        for key, value in one.items():
            total[key] = total[key] + value
    receipts = total["receipts"]
    total["summary"] = {
        "metric": f"{len(total['presented_as_complete'])} of {total['responses']} search responses "
                  f"({total['partial_responses']} partial) presented as complete",
        "statement_claims": len(total["statement_claims"]),
        "receipts_delivered_same_turn": f"{sum(r['delivered_same_turn'] for r in receipts)} of {len(receipts)}",
        "receipts_by_tool": sum(r["by_tool_receipt"] for r in receipts),
        "receipts_ref_in_model_text": sum(r["ref_in_model_text"] for r in receipts),
        "silent_completions": len(total["silent_completions"]),
    }
    (run / "case-metric.json").write_text(json.dumps(total, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(total["summary"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
