"""Read-only decisions from fictional service records; no model or payment."""
from dataclasses import dataclass


@dataclass(frozen=True)
class ReturnRecord:
    order_ref: str
    customer_id: str
    paid_minor: int
    received_day: int
    condition: str | None = None
    inspection_ref: str | None = None

    def __post_init__(self):
        if type(self.paid_minor) is not int or self.paid_minor <= 0:
            raise ValueError("paid_minor must be a positive integer")
        if type(self.received_day) is not int or self.received_day < 0:
            raise ValueError("received_day must be a non-negative integer")


def assess_refund(record: ReturnRecord | None, customer_id: str) -> dict:
    """Apply REFUND-POLICY.md to a looked-up order, not customer-supplied facts."""
    if record is None or record.customer_id != customer_id:
        return {"status": "unknown_order"}
    if record.received_day > 30:
        return {"status": "staff_review", "reason": "outside_automatic_window"}
    if not record.inspection_ref or record.condition is None:
        return {"status": "awaiting_inspection"}
    if record.condition not in {"sealed", "confirmed_defect"}:
        return {"status": "staff_review", "reason": "condition_needs_review"}
    return {"status": "full_refund_offer", "amount_minor": record.paid_minor,
            "currency": "GBP"}
