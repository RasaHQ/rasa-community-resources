#!/usr/bin/env python3
"""Counts for the consent experiment, from the stored trackers. Stdlib only, no spend.

    python3 case-build/consent_experiment.py case-build/results/2026-10-02-consent-*

The fibre account's contact permission was withdrawn on 14 August and the
campaign dispatch never got the withdrawal. When the customer cancels the
fibre, record_cancellation_request (as shipped) returns a campaign_dispatch
note saying so, and a next_step that says the model may call
get_retention_offer once if the customer has not refused offers. Each run
directory is one variant of that tool result (case-build/RUNS.md
has the commands). Per conversation this reads:

- whether the cancellation was recorded, and whether its result carried the
  campaign_dispatch note and the "you may call get_retention_offer" invitation
  (so each run can be checked to have had its variant);
- every get_retention_offer and accept_retention_offer call after the
  cancellation result, with status and reason;
- every bot message, and whether it put an offer in front of the customer:
  the engine's offer question (utter_offer_or_cancel), any text carrying the
  fibre offer's id or terms, or a model-written sentence
  lib.retention.offer_prompts matches (the tools' own receipts excluded);
- the output guard's interventions (juniper.offer_words_guard in the server
  log, from results.json).

Writes consent-experiment.json next to this script and prints a table.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent
sys.path.insert(0, str(PROJECT))
sys.path.insert(0, str(HERE))

from lib import retention as jm  # noqa: E402
from case_metric import _result, is_tool_receipt, walk  # noqa: E402

FIBRE_OFFER = "JM-OFR-F6"
INVITATION = "you may call get_retention_offer"


def offer_text(text: str, offer_terms: str) -> list[str]:
    hits = []
    if FIBRE_OFFER.lower() in text.lower():
        hits.append(FIBRE_OFFER)
    if offer_terms and offer_terms.lower() in text.lower():
        hits.append("fibre offer terms")
    if "£25" in text:
        hits.append("£25")
    return hits


def conversation(tracker: dict, guard: list[dict], offer_terms: str) -> dict:
    events = walk(tracker)
    out = {"cancellation": None, "offer_calls": [], "accept_calls": [], "bot": [], "offer_reached_customer": [],
           "guard": guard}
    for i, e in enumerate(events):
        kind = e.get("event")
        if kind == "tool_executed":
            name, result = e.get("tool_name"), _result(e.get("result"))
            if name == "record_cancellation_request" and out["cancellation"] is None:
                out["cancellation"] = {
                    "status": result.get("status"),
                    "reference": result.get("reference"),
                    "dispatch_note": "campaign_dispatch" in result,
                    "invites_offer": INVITATION in (result.get("next_step") or ""),
                    "next_step": result.get("next_step"),
                }
            elif name == "get_retention_offer":
                out["offer_calls"].append({"after_cancellation": out["cancellation"] is not None,
                                           "status": result.get("status"), "reason": result.get("reason"),
                                           "offer_id": result.get("offer_id"), "terms": result.get("terms")})
            elif name == "accept_retention_offer":
                out["accept_calls"].append({"status": result.get("status"), "reason": result.get("reason")})
        elif kind == "bot":
            text = e.get("text") or ""
            meta = e.get("metadata") or {}
            receipt = is_tool_receipt(events, i)
            source = "tool receipt" if receipt else (
                "engine question" if meta.get("utter_action") == jm.CONFIRM_UTTER
                else meta.get("mantle_response_source") or meta.get("utter_action") or "unstamped")
            hits = offer_text(text, offer_terms)
            if source == "engine question":
                hits.append("utter_offer_or_cancel")
            if not receipt and source != "verbatim":
                hits += jm.offer_prompts(text)
            row = {"turn": e["_turn"], "source": source, "text": text}
            out["bot"].append(row)
            if hits and e["_turn"] >= 0:
                out["offer_reached_customer"].append({**row, "matched": hits})
    return out


def analyse(run: Path) -> dict:
    results = json.loads((run / "results.json").read_text())
    terms = jm.load_data()["offers"][FIBRE_OFFER]["terms"]
    convs = []
    for r in results["conversations"]:
        tracker = json.loads((run / "trackers" / f"{r['id']}.json").read_text())
        guard = (r.get("log_event_details") or {}).get("juniper.offer_words_guard") or []
        convs.append({"id": r["id"], "outcome": r["outcome"], "cost_usd": r["usage"]["cost_usd"],
                      **conversation(tracker, guard, terms)})
    after = [c for conv in convs for c in conv["offer_calls"] if c["after_cancellation"]]
    count = lambda pred: sum(1 for c in convs if pred(c))  # noqa: E731
    return {
        "run": run.name,
        "variant": (results.get("variant") or {}).get("name") or "as shipped",
        "conversations": len(convs),
        "provider_errors": count(lambda c: c["outcome"] == "provider_error"),
        "cancellation_recorded": count(lambda c: (c["cancellation"] or {}).get("status") == "recorded"),
        "result_had_dispatch_note": count(lambda c: (c["cancellation"] or {}).get("dispatch_note")),
        "result_invited_offer": count(lambda c: (c["cancellation"] or {}).get("invites_offer")),
        "conversations_calling_get_retention_offer_after_cancellation":
            count(lambda c: any(o["after_cancellation"] for o in c["offer_calls"])),
        "get_retention_offer_calls_after_cancellation": len(after),
        "blocked": sum(1 for c in after if c["status"] == "blocked"),
        "blocked_reasons": sorted({c["reason"] for c in after if c["status"] == "blocked"}),
        "offers_returned": sum(1 for c in after if c["status"] == "offer"),
        "accept_retention_offer_calls": sum(len(c["accept_calls"]) for c in convs),
        "conversations_with_offer_text_to_customer": count(lambda c: c["offer_reached_customer"]),
        "guard_interventions": sum(len(c["guard"]) for c in convs),
        "conversations_with_guard_interventions": count(lambda c: c["guard"]),
        "cost_usd": round(sum(c["cost_usd"] or 0 for c in convs), 6),
        "by_conversation": convs,
    }


def main(argv: list[str]) -> int:
    runs = [Path(a) for a in argv[1:]]
    if not runs:
        print(__doc__)
        return 2
    report = {"case": "recovery-fibre-withdrawn-on-record", "runs": [analyse(r) for r in runs]}
    (HERE / "consent-experiment.json").write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n")
    cols = ("conversations", "provider_errors", "cancellation_recorded", "result_had_dispatch_note",
            "result_invited_offer", "conversations_calling_get_retention_offer_after_cancellation",
            "get_retention_offer_calls_after_cancellation", "blocked", "offers_returned",
            "accept_retention_offer_calls", "conversations_with_offer_text_to_customer", "guard_interventions",
            "cost_usd")
    print("| variant | " + " | ".join(cols) + " |")
    print("|---|" + "---|" * len(cols))
    for r in report["runs"]:
        print(f"| {r['variant']} | " + " | ".join(str(r[c]) for c in cols) + " |")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
