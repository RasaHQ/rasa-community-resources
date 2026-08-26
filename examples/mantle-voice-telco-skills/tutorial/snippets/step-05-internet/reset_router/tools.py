"""Reset-router skill tools (auto-discovered)."""

from __future__ import annotations

from datetime import datetime

from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult

from lib.database import Database, customer_id_from_context


@tool(description="List routers registered to the current customer.")
async def list_routers(context: ToolContext = None) -> ToolResult:
    """List the customer's routers with model and status."""
    customer_id = customer_id_from_context(context)
    db = Database()
    rows = db.run_query(
        """
        SELECT device_id, model, status, wifi_name
        FROM routers WHERE customer_id = ?
        """,
        (customer_id,),
        one_record=False,
    )
    routers = [
        {
            "device_id": device_id,
            "model": model,
            "status": status,
            "wifi_name": wifi_name,
        }
        for device_id, model, status, wifi_name in rows or []
    ]
    if context is not None:
        context.memory.set("routers_loaded", True)
    return ToolResult(
        llm_response={"ok": True, "routers": routers, "router_count": len(routers)}
    )


@tool(description="Remotely factory-reset a customer router. This wipes Wi-Fi settings.")
async def factory_reset_router(device_id: str, context: ToolContext = None) -> ToolResult:
    """Factory-reset a router by device id.

    Args:
        device_id: Router device id such as RTR-123-01.
    """
    customer_id = customer_id_from_context(context)
    db = Database()
    row = db.run_query(
        """
        SELECT device_id, model, wifi_name
        FROM routers WHERE customer_id = ? AND device_id = ?
        """,
        (customer_id, device_id),
        one_record=True,
    )
    if not row:
        return ToolResult(
            llm_response={
                "ok": False,
                "error": "router_not_found",
                "device_id": device_id,
                "hint": "Ask the customer which router to reset from their registered devices.",
            }
        )

    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    db.cursor.execute(
        """
        UPDATE routers
        SET status = 'resetting', last_reset_at = ?, wifi_name = NULL
        WHERE device_id = ? AND customer_id = ?
        """,
        (now, device_id, customer_id),
    )
    db.cursor.execute(
        """
        UPDATE routers
        SET status = 'online', wifi_name = 'TelecomOfRasa-Setup'
        WHERE device_id = ? AND customer_id = ?
        """,
        (device_id, customer_id),
    )
    db.commit()

    device_id_val, model, _old_wifi = row
    if context is not None:
        context.memory.set("router_reset", True)
        context.memory.set("selected_device_id", device_id_val)
        context.memory.set("selected_device_label", model)

    return ToolResult(
        llm_response={
            "ok": True,
            "device_id": device_id_val,
            "model": model,
            "status": "online",
            "wifi_name": "TelecomOfRasa-Setup",
            "message": (
                "Factory reset complete. The Wi-Fi name was restored to "
                "TelecomOfRasa-Setup. The customer may need to reconnect devices."
            ),
        }
    )
