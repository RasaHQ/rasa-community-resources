"""Global tools — available to every skill without an explicit import_tools."""

from __future__ import annotations

from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult

from lib.bank import CUSTOMER


@tool(
    description=(
        "Load the signed-in customer's profile into project memory. Runs once "
        "at session start, before the greeting."
    )
)
async def load_customer_profile(context: ToolContext = None) -> ToolResult:
    """Seed project memory so no skill has to ask who it is talking to."""
    if context is not None:
        # Bare keys resolve to the root-declared project entries
        # (session.project.*). The prefixed form is rejected at train time as
        # an undeclared memory write.
        context.memory.set("customer_name", CUSTOMER["name"])
        context.memory.set("customer_id", CUSTOMER["customer_id"])
    return ToolResult(
        llm_response={
            "ok": True,
            "customer_name": CUSTOMER["name"],
            "customer_id": CUSTOMER["customer_id"],
        }
    )
