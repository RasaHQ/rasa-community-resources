"""Order-status tools. The guard runs in lib.orders, not in the prompt.

The customer id comes from project memory (written by load_session_customer).
The model passes an order number and, for a split order, a parcel number.
"""

from __future__ import annotations

from typing import Optional

from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult

from lib import orders


def _customer(context: Optional[ToolContext]) -> str:
    return (
        context.memory.get("project.customer_id") if context is not None else None
    ) or orders.SESSION_CUSTOMER_ID


@tool(
    description=(
        "List the signed-in customer's orders: order numbers, items and how many "
        "parcels each was split into. No tracking status. Use it when the "
        "customer names an item instead of an order number."
    )
)
async def list_orders(context: ToolContext = None) -> ToolResult:
    return ToolResult(llm_response=orders.list_orders(_customer(context)))


@tool(
    description=(
        "Tracking status of one parcel of one of the customer's orders: the "
        "latest milestone, who observed it (warehouse or carrier scan) and when, "
        "whether the carrier has the parcel, whether it was delivered, any "
        "estimate (labelled as an estimate) and a status reference. For an order "
        "split into several parcels, pass parcel_number; each parcel has its own "
        "status."
    )
)
async def track_order(
    order_number: str, parcel_number: Optional[int] = None, context: ToolContext = None
) -> ToolResult:
    """Track one parcel.

    Args:
        order_number: The order number as digits, for example WS-10482 or 10482.
        parcel_number: Which parcel of a split order, 1 or 2. Leave empty for a single-parcel order.
    """
    return ToolResult(llm_response=orders.track_order(_customer(context), order_number, parcel_number))


@tool(
    description=(
        "Pass one parcel to Willow Shop delivery support when the customer wants "
        "help with a delay or the tracking cannot be given. Returns a reference, "
        "the last observed event with its age, and no arrival prediction."
    )
)
async def open_delivery_help(
    order_number: str, parcel_number: Optional[int] = None, context: ToolContext = None
) -> ToolResult:
    """Open a delivery-help request.

    Args:
        order_number: The order number as digits, for example WS-10560.
        parcel_number: Which parcel of a split order, 1 or 2. Leave empty for a single-parcel order.
    """
    return ToolResult(llm_response=orders.delivery_help(_customer(context), order_number, parcel_number))
