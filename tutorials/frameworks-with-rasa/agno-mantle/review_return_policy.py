"""Literal invented policy examples; standard-library only, no model client."""
import argparse
import json
from dataclasses import replace
from shop_adviser.refund_policy import ReturnRecord, assess_refund, has_inspection


def policy_examples():
    order = ReturnRecord("WS-REVIEW-01", "customer-a", 1299, 30,
                         "sealed", "inspection-review-01")
    offer = {"status": "full_refund_offer", "amount_minor": 1299, "currency": "GBP"}
    late = {"status": "staff_review", "reason": "outside_automatic_window"}
    absent = replace(order, condition=None, inspection_ref=None)
    return [
        ("sealed, last included day", order, "customer-a", offer),
        ("sealed, first excluded day", replace(order, received_day=31), "customer-a", late),
        ("no inspection, last included day", absent, "customer-a", {"status": "awaiting_inspection"}),
        ("no inspection, first excluded day", replace(absent, received_day=31), "customer-a", late),
        ("opened, last included day", replace(order, condition="opened"), "customer-a",
         {"status": "staff_review", "reason": "condition_needs_review"}),
        ("another customer's order", order, "customer-b", {"status": "unknown_order"}),
        ("missing order", None, "customer-a", {"status": "unknown_order"}),
    ]


def review_examples():
    rows = []
    for label, record, customer, expected in policy_examples():
        actual = assess_refund(record, customer)
        if actual != expected:
            raise AssertionError(f"{label}: expected {expected!r}, got {actual!r}")
        rows.append({"case": label,
                     "received_day": record.received_day if record else None,
                     "condition": record.condition if record else None,
                     "inspection_recorded": has_inspection(record),
                     "customer_matches_order": bool(record and record.customer_id == customer),
                     "result": actual})
    return rows


def validate_review_note(note, record):
    """Check a proposed local worksheet contract, not an authenticated queue."""
    if type(note.get("inspection_recorded")) is not bool:
        raise ValueError("review note needs an explicit inspection status")
    inspected = has_inspection(record)
    if note["inspection_recorded"] != inspected:
        raise ValueError("inspection status disagrees with the source record")
    expected = "review_exception" if inspected else "obtain_inspection"
    if note.get("next_step") != expected:
        raise ValueError("next step disagrees with the recorded inspection status")
    if note.get("receiving_role") != "returns-reviewer" or note.get("delivery") != "draft_not_sent":
        raise ValueError("this worksheet creates local drafts only")
    return note


def draft_review_notes(rows):
    """Worked fictional choice: collect inspection before reviewing a late return."""
    notes = []
    records = {label: record for label, record, _, _ in policy_examples()}
    for row in rows:
        if row["result"].get("reason") != "outside_automatic_window":
            continue
        inspected = row["inspection_recorded"]
        note = {"case": row["case"], "policy_result": row["result"],
                "inspection_recorded": inspected,
                "next_step": "review_exception" if inspected else "obtain_inspection",
                "receiving_role": "returns-reviewer", "delivery": "draft_not_sent"}
        notes.append(validate_review_note(note, records[row["case"]]))
    return notes


def review_sheet():
    rows = review_examples()
    notes = draft_review_notes(rows)
    records = {label: record for label, record, _, _ in policy_examples()}
    incomplete = {k: v for k, v in notes[0].items() if k != "inspection_recorded"}
    try:
        validate_review_note(incomplete, records[incomplete["case"]])
    except ValueError as error:
        control = {"changed": "removed inspection_recorded", "result": "rejected",
                   "reason": str(error)}
    else:
        raise AssertionError("An incomplete review note was accepted")
    wrong_step = {**notes[1], "next_step": "review_exception"}
    try:
        validate_review_note(wrong_step, records[wrong_step["case"]])
    except ValueError as error:
        step_control = {"changed": "skip missing inspection", "result": "rejected",
                        "reason": str(error)}
    else:
        raise AssertionError("A note skipped its missing inspection")
    forged = {**notes[1], "inspection_recorded": True, "next_step": "review_exception"}
    try:
        validate_review_note(forged, records[forged["case"]])
    except ValueError as error:
        status_control = {"changed": "falsify inspection and next step", "result": "rejected",
                          "reason": str(error)}
    else:
        raise AssertionError("A note invented an inspection")
    return {"policy": "fictional Willow Shop automatic returns", "cases": rows,
            "proposed_review_notes": notes, "incomplete_note_control": control,
            "wrong_next_step_control": step_control,
            "false_inspection_control": status_control}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    display = parser.add_mutually_exclusive_group()
    display.add_argument("--cases-only", action="store_true")
    display.add_argument("--notes-only", action="store_true")
    args = parser.parse_args()
    sheet = review_sheet()
    if args.cases_only:
        sheet = {key: sheet[key] for key in ("policy", "cases")}
    elif args.notes_only:
        sheet = {key: value for key, value in sheet.items() if key != "cases"}
    print(json.dumps(sheet, indent=2))
