"""Local tools for the check_claim_status skill (auto-discovered)."""

from __future__ import annotations

from rasa.calm_v2.tools.decorator import ToolContext, tool
from rasa.calm_v2.tools.result import ToolResult

from lib.database import (
    CLAIM_STATUS_LABELS,
    Database,
    adjustor_date_from_claim,
    customer_id_from_context,
)


@tool(description="Look up an existing claim by claim number for the current customer.")
async def get_claim_status(claim_number: str, context: ToolContext = None) -> ToolResult:
    """Look up claim status by claim number.

    Args:
        claim_number: The claim id to look up (for example CLAIM1236).
    """
    customer_id = customer_id_from_context(context)
    db = Database()
    normalized = claim_number.strip().upper()
    row = db.run_query(
        """
        SELECT claim_id, policy_num, claim_date, claim_status, inspection_date
        FROM claims
        WHERE customer_id = ? AND upper(claim_id) = ?
        """,
        (customer_id, normalized),
        one_record=True,
    )
    if not row:
        if context is not None:
            context.memory.set("claim_status", "5")
            context.memory.set("claim_status_label", CLAIM_STATUS_LABELS[5])
            context.memory.set("claim_number", normalized)
        return ToolResult(
            llm_response={
                "ok": False,
                "error": "claim_not_found",
                "claim_number": normalized,
                "claim_status": 5,
                "claim_status_label": CLAIM_STATUS_LABELS[5],
                "hint": "Ask the customer to confirm the claim number.",
            }
        )

    claim_id, policy_num, claim_date, claim_status, inspection_date = row
    status_int = int(claim_status)
    adjustor_date = adjustor_date_from_claim(claim_date or "")
    label = CLAIM_STATUS_LABELS.get(status_int, "unknown")

    if context is not None:
        context.memory.set("claim_number", claim_id)
        context.memory.set("claim_status", str(status_int))
        context.memory.set("claim_status_label", label)
        context.memory.set("adjustor_date", adjustor_date)
        context.memory.set("policy_num", policy_num)
        if inspection_date:
            context.memory.set("inspection_date", inspection_date)

    return ToolResult(
        llm_response={
            "ok": True,
            "claim_number": claim_id,
            "policy_num": policy_num,
            "claim_date": claim_date,
            "claim_status": status_int,
            "claim_status_label": label,
            "adjustor_date": adjustor_date,
            "inspection_date": inspection_date,
            "adjustor_contact": {
                "name": "John Doe",
                "phone": "+1 222 333 4567",
            }
            if status_int == 1
            else None,
        }
    )
