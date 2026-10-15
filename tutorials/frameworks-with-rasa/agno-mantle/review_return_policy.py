"""Literal invented policy examples; standard-library only, no model client."""
import json
from dataclasses import replace
from shop_adviser.refund_policy import ReturnRecord, assess_refund


def review_examples():
    order = ReturnRecord("WS-REVIEW-01", "customer-a", 1299, 30,
                         "sealed", "inspection-review-01")
    offer = {"status": "full_refund_offer", "amount_minor": 1299, "currency": "GBP"}
    late = {"status": "staff_review", "reason": "outside_automatic_window"}
    absent = replace(order, condition=None, inspection_ref=None)
    cases = [
        ("sealed, last included day", order, "customer-a", offer),
        ("sealed, first excluded day", replace(order, received_day=31), "customer-a", late),
        ("no inspection, last included day", absent, "customer-a", {"status": "awaiting_inspection"}),
        ("no inspection, first excluded day", replace(absent, received_day=31), "customer-a", late),
        ("opened, last included day", replace(order, condition="opened"), "customer-a",
         {"status": "staff_review", "reason": "condition_needs_review"}),
        ("another customer's order", order, "customer-b", {"status": "unknown_order"}),
        ("missing order", None, "customer-a", {"status": "unknown_order"}),
    ]
    rows = []
    for label, record, customer, expected in cases:
        actual = assess_refund(record, customer)
        if actual != expected:
            raise AssertionError(f"{label}: expected {expected!r}, got {actual!r}")
        rows.append({"case": label,
                     "received_day": record.received_day if record else None,
                     "condition": record.condition if record else None,
                     "inspection_recorded": bool(record and record.inspection_ref),
                     "customer_matches_order": bool(record and record.customer_id == customer),
                     "result": actual})
    return rows


if __name__ == "__main__":
    print(json.dumps({"policy": "fictional Willow Shop automatic returns",
                      "cases": review_examples()}, indent=2))
