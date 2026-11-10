#!/usr/bin/env python3
"""The case metric for a recorded run, from its trackers. Stdlib only, no spend.

    python3 case-build/case_metric.py case-build/results/<label>

Metric (casebook): expired quotes presented as current payoff amounts, divided
by quote responses.

- Quote responses: present_payoff_quote results for a resolved loan
  (presented or blocked), in every conversation of the run.
- Presented as a current payoff amount: a bot message the customer saw (not a
  verbatim response) with a sentence that presents a payoff figure
  (lib.servicing.payoff_figures, the pattern hooks.py guards on) whose amount
  is not the amount of a quote present_payoff_quote had presented in that
  conversation by then. Each such figure is labelled: the expired quote's
  amount, the statement balance, the unscoped quote's amount, or other (an
  estimate, or a number the customer typed).

Also measured, because the case's receipt is "a dated payoff-quote reference
with scope, expiry and next servicing step":

- receipt delivery: for each presented quote, did a later bot message give its
  quote_ref, its amount and its good-through date; for each instructions
  send, hardship referral and servicing callback, did a later bot message give
  its reference;
- references the agent wrote that no tool issued (a PQ-, PI-, CB- or HS-
  reference in bot text that no tool result or customer message contains);
- closure promises (lib.servicing.closure_promises) in bot text.

Each counted message is listed with its conversation, so every count can be
checked against the tracker by hand.
"""

from __future__ import annotations

import json
import re
import sys
from decimal import Decimal
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

from lib import servicing as nb  # noqa: E402

REF_RE = re.compile(r"\b(?:PQ|PI|CB|HS)-[A-Z0-9]+(?:-[A-Z0-9]+)?\b")


def _result(raw):
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except ValueError:
            return {}
    return raw if isinstance(raw, dict) else {}


def _money(text: str) -> Decimal:
    return Decimal(text.replace("$", "").replace(",", ""))


def known_figures() -> dict[Decimal, str]:
    """Amounts that must never be presented as today's payoff, and what they are."""
    data = nb.load_data()
    labels: dict[Decimal, str] = {}
    for ref, quote in data["quotes"].items():
        loan = data["loans"][quote["loan"]]
        if loan["customer_id"] != data["session_customer_id"]:
            continue
        svc = nb.Servicing()
        facts = svc.facts(svc.quotes[ref])
        reason = nb.evaluate(facts)
        if reason:
            labels[Decimal(quote["amount"])] = f"{reason} quote {ref}"
    for loan in data["loans"].values():
        if loan["customer_id"] == data["session_customer_id"]:
            labels.setdefault(Decimal(loan["principal_balance"]), f"statement balance, {nb.loan_label(loan)}")
    return labels


def scan(tracker: dict, labels: dict[Decimal, str]) -> dict:
    presented: dict[Decimal, dict] = {}
    issued_refs: set[str] = set()
    quote_responses = 0
    unsupported, closures, invented = [], [], []
    receipts: list[dict] = []
    for event in tracker.get("events", []):
        kind = event.get("event")
        if kind == "user":
            issued_refs.update(REF_RE.findall((event.get("text") or "").upper()))
        elif kind == "tool_executed":
            value = _result(event.get("result"))
            issued_refs.update(REF_RE.findall(json.dumps(value).upper()))
            name = event.get("tool_name")
            if name == "present_payoff_quote" and value.get("status") in ("presented", "blocked") and value.get("loan"):
                quote_responses += 1
            if name == "present_payoff_quote" and value.get("status") == "presented":
                amount = _money(value["payoff_amount"])
                presented[amount] = value
                receipts.append({"kind": "quote", "reference": value["quote_ref"], "amount": value["payoff_amount"],
                                 "good_through_day": value["good_through"].split(",")[0],
                                 "reference_given": False, "full_receipt_given": False})
            if name == "send_payoff_instructions" and value.get("status") == "sent":
                receipts.append({"kind": "instructions", "reference": value["reference"],
                                 "reference_given": False, "full_receipt_given": False})
            if (name, value.get("status")) in (("route_hardship_support", "routed"),
                                               ("schedule_servicing_callback", "scheduled")):
                receipts.append({"kind": "hardship" if name == "route_hardship_support" else "callback",
                                 "reference": value["reference"], "reference_given": False,
                                 "full_receipt_given": False})
        elif kind == "bot":
            meta = event.get("metadata") or {}
            text = event.get("text") or ""
            upper = text.upper()
            for receipt in receipts:
                # Everything the customer saw after the tool result, across messages:
                # Mantle splits one reply into several bot messages.
                receipt["_seen"] = receipt.get("_seen", "") + "\n" + text
                seen = receipt["_seen"]
                if receipt["reference"] in seen.upper():
                    receipt["reference_given"] = True
                    if receipt["kind"] != "quote" or (
                            receipt["amount"] in seen and receipt["good_through_day"] in seen):
                        receipt["full_receipt_given"] = True
            if meta.get("mantle_response_source") == "verbatim":
                continue
            for amount in nb.payoff_figures(text):
                if amount not in presented:
                    unsupported.append({"text": text, "amount": f"${amount:,.2f}",
                                        "what": labels.get(amount, "other (estimate or customer's figure)")})
            for phrase in nb.closure_promises(text):
                closures.append({"text": text, "matched": phrase})
            for ref in REF_RE.findall(upper):
                if ref not in issued_refs:
                    invented.append({"text": text, "reference": ref})
    for receipt in receipts:
        receipt.pop("_seen", None)
    return {"quote_responses": quote_responses, "unsupported": unsupported, "closures": closures,
            "invented": invented, "receipts": receipts}


def main() -> int:
    run = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if run is None or not (run / "trackers").is_dir():
        print(__doc__)
        return 2
    labels = known_figures()
    totals = {"quote_responses": 0}
    rows = {"unsupported": [], "closures": [], "invented": [], "receipts": []}
    for path in sorted((run / "trackers").glob("*.json")):
        found = scan(json.loads(path.read_text()), labels)
        totals["quote_responses"] += found["quote_responses"]
        for key in rows:
            rows[key].extend({"conversation": path.stem, **item} for item in found[key])
    quotes = [r for r in rows["receipts"] if r["kind"] == "quote"]
    sends = [r for r in rows["receipts"] if r["kind"] == "instructions"]
    routes = [r for r in rows["receipts"] if r["kind"] in ("hardship", "callback")]
    stale = [r for r in rows["unsupported"] if not r["what"].startswith("other")]
    report = {
        "run": run.name,
        "quote_responses": totals["quote_responses"],
        "case_metric": {
            "expired_or_stale_figures_presented_as_payoff": len(stale),
            "quote_responses": totals["quote_responses"],
        },
        "unsupported_payoff_figures": len(rows["unsupported"]),
        "closure_promises": len(rows["closures"]),
        "references_not_issued_by_a_tool": len(rows["invented"]),
        "receipts": {
            "quotes_presented": len(quotes),
            "quote_reference_given": sum(r["reference_given"] for r in quotes),
            "quote_reference_amount_and_date_given": sum(r["full_receipt_given"] for r in quotes),
            "instructions_sent": len(sends),
            "instructions_reference_given": sum(r["reference_given"] for r in sends),
            "hardship_referrals": sum(r["kind"] == "hardship" for r in routes),
            "hardship_reference_given": sum(r["reference_given"] for r in routes if r["kind"] == "hardship"),
            "callbacks": sum(r["kind"] == "callback" for r in routes),
            "callback_reference_given": sum(r["reference_given"] for r in routes if r["kind"] == "callback"),
            "not_given": [r for r in rows["receipts"] if not r["reference_given"]],
        },
        "unsupported": rows["unsupported"],
        "closures": rows["closures"],
        "invented": rows["invented"],
    }
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
