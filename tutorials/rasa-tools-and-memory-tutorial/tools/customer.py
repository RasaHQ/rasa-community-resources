"""GLOBAL tools — shared across skills, imported explicitly by each one.

A tool belongs here when it passes all three tests:

  1. more than one skill calls it,
  2. it is skill-agnostic — it does not know why it was called,
  3. it is about the end user rather than one skill's workflow.

`get_customer_info` passes: both check_balance and transfer_money need the
customer's name and segment, and neither owns that lookup. It lives at the
project root so it is discoverable, and each skill names it in `import_tools`
so the dependency stays explicit and the skill folder stays portable.
"""

from __future__ import annotations

from lib.engine import ToolContext, ToolResult, tool

from lib.directory import customer_by_id


@tool(
    description=(
        "Look up the signed-in customer's profile (name and segment). "
        "Requires that the customer has already been authenticated."
    )
)
async def get_customer_info(context: ToolContext = None) -> ToolResult:
    """Return profile details for the authenticated customer."""
    customer_id = None
    if context is not None:
        customer_id = context.memory.get("project.customer_id")

    if not customer_id:
        return ToolResult(
            llm_response={
                "ok": False,
                "error": "not_authenticated",
                "hint": "Run the authentication skill before calling this tool.",
            }
        )

    customer = customer_by_id(str(customer_id))
    if customer is None:
        return ToolResult(llm_response={"ok": False, "error": "customer_not_found"})

    return ToolResult(
        llm_response={
            "ok": True,
            "customer_id": customer["customer_id"],
            "name": customer["name"],
            "segment": customer["segment"],
        }
    )
