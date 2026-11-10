"""Synthetic results only; no external system, email, note or staff queue."""

def refuse():
    return {"status": "refused", "reason": "manual_review_required"}


def handoff():
    return {"status": "demo_handoff", "reference": "HANDOFF-DEMO"}


def detour(name):
    return {"status": "detour_attempted", "tool": name}
