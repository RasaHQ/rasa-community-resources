"""Shared insurance tools (used by 2+ skills or session start).

Single-skill tools live in skills/<name>/tools.py and are auto-discovered.
"""

from __future__ import annotations

from typing import Optional

from rasa.calm_v2.tools.decorator import ToolContext, tool
from rasa.calm_v2.tools.result import ToolResult

from lib.database import Database, customer_id_from_context, get_customer


@tool(description="Load the demo customer profile into project memory.")
async def load_customer_profile(context: ToolContext = None) -> ToolResult:
    """Ensure customer_id / name fields are available in session.project.*."""
    customer_id = customer_id_from_context(context)
    db = Database()
    row = get_customer(db, customer_id)
    if not row:
        return ToolResult(
            llm_response={
                "ok": False,
                "error": "customer_not_found",
                "customer_id": customer_id,
            }
        )

    cid, first_name, last_name = row
    if context is not None:
        context.memory.set("customer_id", cid)
        context.memory.set("customer_first_name", first_name)
        context.memory.set("customer_last_name", last_name)

    return ToolResult(
        llm_response={
            "ok": True,
            "customer_id": cid,
            "customer_first_name": first_name,
            "customer_last_name": last_name,
            "display_name": f"{first_name} {last_name}",
        }
    )


@tool(description="List the customer's insurance policies with premium and coverage limit.")
async def list_policies(context: ToolContext = None) -> ToolResult:
    """List policies for the active customer."""
    customer_id = customer_id_from_context(context)
    db = Database()
    rows = db.run_query(
        """
        SELECT policy_type, policy_num, expiration_date, premium, coverage_limit
        FROM policies WHERE customer_id = ?
        ORDER BY policy_type
        """,
        (customer_id,),
        one_record=False,
    )
    policies = [
        {
            "policy_type": policy_type,
            "policy_num": policy_num,
            "expiration_date": expiration_date,
            "premium": float(premium),
            "coverage_limit": float(coverage_limit),
        }
        for policy_type, policy_num, expiration_date, premium, coverage_limit in rows
        or []
    ]
    return ToolResult(
        llm_response={
            "ok": True,
            "policies": policies,
            "policy_count": len(policies),
            "customer_id": customer_id,
        }
    )
