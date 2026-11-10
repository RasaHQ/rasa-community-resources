"""Invented Willow Shop order/inspection records, not customer-supplied facts."""
from .refund_policy import ReturnRecord

RETURNS = {
    "WS-RETURN-01": ReturnRecord("WS-RETURN-01", "customer-a", 1299, 20, "sealed", "inspection-01"),
    "WS-RETURN-LATE": ReturnRecord("WS-RETURN-LATE", "customer-a", 1299, 34, "confirmed_defect", "inspection-02"),
    "WS-RETURN-PENDING": ReturnRecord("WS-RETURN-PENDING", "customer-a", 1299, 20),
    "WS-RETURN-B": ReturnRecord("WS-RETURN-B", "customer-b", 899, 10, "sealed", "inspection-03"),
}


def find_return(order_ref: str) -> ReturnRecord | None:
    return RETURNS.get(order_ref)
