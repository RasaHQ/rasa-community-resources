"""Parts-order skill tools â€” local to skills/parts_order/."""

from __future__ import annotations

from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult

from lib.database import Database, get_part, next_order_id
from lib.tool_helpers import active_tech_id


def _selected_call_ref(context: ToolContext) -> str:
    """Best-effort call reference from project memory, or UNASSIGNED."""
    if context is None:
        return "UNASSIGNED"
    ref = context.memory.get("selected_job_ref")
    return str(ref) if ref else "UNASSIGNED"


@tool(description="Check parts stock, price, and whether approval is required.")
async def check_part_stock(
    part_no: str, context: ToolContext = None
) -> ToolResult:
    """Look up a part in the inventory.

    Args:
        part_no: Part number such as HYD-PUMP-90.
    """
    cleaned = str(part_no).strip().upper().replace(" ", "")
    db = Database()
    part = get_part(db, cleaned)
    if not part:
        return ToolResult(
            llm_response={"ok": False, "error": "part_not_found", "part_no": cleaned}
        )

    pno, pname, price, qty, restricted = part
    if context is not None:
        context.memory.set("part_no", pno)
        context.memory.set("part_is_restricted", bool(restricted))
        context.memory.set("unit_price", price)

    return ToolResult(
        llm_response={
            "ok": True,
            "part_no": pno,
            "part_name": pname,
            "unit_price": price,
            "qty_on_hand": qty,
            "restricted": bool(restricted),
            "approval_required": bool(restricted),
        }
    )


@tool(description="Place a parts order for a confirmed, non-restricted part.")
async def submit_parts_order(
    part_no: str, qty: int, context: ToolContext = None
) -> ToolResult:
    """Create a parts order.

    Args:
        part_no: Part number to order.
        qty: Quantity to order.
    """
    tech_id = active_tech_id(context)
    cleaned = str(part_no).strip().upper().replace(" ", "")
    db = Database()
    part = get_part(db, cleaned)
    if not part:
        return ToolResult(
            llm_response={"ok": False, "error": "part_not_found", "part_no": cleaned}
        )

    pno, pname, _price, _qty, restricted = part
    if restricted:
        return ToolResult(
            llm_response={
                "ok": False,
                "error": "requires_approval",
                "part_no": pno,
            }
        )

    call_ref = _selected_call_ref(context)
    order_id = next_order_id(db)
    db.connection.execute(
        """
        INSERT INTO parts_orders (tech_id, call_ref, order_id, part_no, qty, status)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (tech_id, call_ref, order_id, pno, int(qty), "ordered"),
    )
    db.commit()
    db.save_to_disk()

    if context is not None:
        context.memory.set("order_ref", order_id)

    spoken = " ".join(list(order_id))
    return ToolResult(
        llm_response={
            "ok": True,
            "order_id": order_id,
            "order_id_spoken": spoken,
            "part_no": pno,
            "part_name": pname,
            "qty": int(qty),
            "call_ref": call_ref,
            "status": "ordered",
        }
    )


@tool(description="Raise an approval request for a restricted part.")
async def request_part_approval(
    part_no: str, qty: int, context: ToolContext = None
) -> ToolResult:
    """Create a pending-approval parts ticket.

    Args:
        part_no: Restricted part number.
        qty: Quantity requested.
    """
    tech_id = active_tech_id(context)
    cleaned = str(part_no).strip().upper().replace(" ", "")
    db = Database()
    part = get_part(db, cleaned)
    if not part:
        return ToolResult(
            llm_response={"ok": False, "error": "part_not_found", "part_no": cleaned}
        )

    pno, pname, _price, _qty, restricted = part
    if not restricted:
        return ToolResult(
            llm_response={
                "ok": False,
                "error": "approval_not_needed",
                "part_no": pno,
            }
        )

    call_ref = _selected_call_ref(context)
    order_id = next_order_id(db)
    db.connection.execute(
        """
        INSERT INTO parts_orders (tech_id, call_ref, order_id, part_no, qty, status)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (tech_id, call_ref, order_id, pno, int(qty), "pending_approval"),
    )
    db.commit()
    db.save_to_disk()

    if context is not None:
        context.memory.set("order_ref", order_id)

    spoken = " ".join(list(order_id))
    return ToolResult(
        llm_response={
            "ok": True,
            "order_id": order_id,
            "order_id_spoken": spoken,
            "part_no": pno,
            "part_name": pname,
            "qty": int(qty),
            "call_ref": call_ref,
            "status": "pending_approval",
        }
    )
