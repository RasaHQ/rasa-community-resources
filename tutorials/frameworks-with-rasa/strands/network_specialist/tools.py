"""Public synthetic network observations, not subscription actions."""
from strands import tool

OBSERVATIONS = {
    "north": {"id": "JM-N-101", "area": "north", "revision": "2026-10-11", "status": "degraded", "advice": "An engineer is investigating the synthetic north-area fault."},
    "south": {"id": "JM-S-201", "area": "south", "revision": "2026-10-11", "status": "normal", "advice": "No synthetic area-wide fault is recorded. Check the device connection."},
}

@tool
def inspect_network(area: str, question: str) -> dict:
    """Read synthetic Juniper Mobile network observations. Does not change subscriptions."""
    if area not in OBSERVATIONS:
        return {"status": "unknown_area"}
    return dict(OBSERVATIONS[area])
