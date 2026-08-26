"""Check-bill skill tools (auto-discovered)."""

from __future__ import annotations

from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult

from lib.database import (
    Database,
    customer_id_from_context,
    month_to_billing_date,
    normalize_month,
)


@tool(description="Summarize a customer's bill for a given month and compare to their average.")
async def get_bill_summary(bill_month: str, context: ToolContext = None) -> ToolResult:
    """Look up bill amount for a month and compare to the customer's average.

    Args:
        bill_month: Month name such as February or Feb.
    """
    customer_id = customer_id_from_context(context)
    month = normalize_month(bill_month)
    bill_date = month_to_billing_date(bill_month)
    if not month or not bill_date:
        return ToolResult(
            llm_response={
                "ok": False,
                "error": "invalid_month",
                "hint": "Ask for a calendar month such as January or February.",
            }
        )

    db = Database()
    rows = db.run_query(
        "SELECT date, amount, source FROM billing WHERE customer_id = ? ORDER BY date",
        (customer_id,),
        one_record=False,
    )
    if not rows:
        return ToolResult(
            llm_response={"ok": False, "error": "no_bills", "customer_id": customer_id}
        )

    specific = [row for row in rows if row[0] == bill_date]
    if not specific:
        return ToolResult(
            llm_response={
                "ok": False,
                "error": "bill_not_found",
                "bill_month": month,
                "bill_date": bill_date,
            }
        )

    bill_amount = float(specific[0][1])
    source = specific[0][2]
    amounts = [float(row[1]) for row in rows]
    average_bill = sum(amounts) / len(amounts)
    difference = bill_amount - average_bill
    comparison = "higher" if difference > 0 else "lower" if difference < 0 else "equal"

    if context is not None:
        context.memory.set("bill_month", month)
        context.memory.set("bill_amount", bill_amount)
        context.memory.set("average_bill", round(average_bill, 2))
        context.memory.set("difference", round(abs(difference), 2))

    return ToolResult(
        llm_response={
            "ok": True,
            "bill_month": month,
            "bill_year": 2026,
            "bill_amount": bill_amount,
            "average_bill": round(average_bill, 2),
            "difference": round(abs(difference), 2),
            "comparison": comparison,
            "source": source,
            "currency": "USD",
        }
    )


@tool(description="List all billing line items for the current customer.")
async def list_bill_charges(context: ToolContext = None) -> ToolResult:
    """Return every billing row for the active customer."""
    customer_id = customer_id_from_context(context)
    db = Database()
    rows = db.run_query(
        "SELECT date, amount, source FROM billing WHERE customer_id = ? ORDER BY date",
        (customer_id,),
        one_record=False,
    )
    charges = [
        {"date": date, "amount": float(amount), "source": source}
        for date, amount, source in rows or []
    ]
    return ToolResult(
        llm_response={
            "ok": True,
            "charges": charges,
            "charge_count": len(charges),
            "currency": "USD",
        }
    )
