"""Local tools for the file_claim skill (auto-discovered)."""

from __future__ import annotations

from datetime import datetime

from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult

from lib.database import Database, customer_id_from_context, normalize_incident_date


@tool(description="Normalize an incident date string to MM/DD/YYYY.")
async def normalize_incident_date_value(
    incident_date: str, context: ToolContext = None
) -> ToolResult:
    """Normalize an incident date.

    Args:
        incident_date: Date as spoken or typed (relative phrases allowed).
    """
    normalized = normalize_incident_date(incident_date)
    if normalized is None:
        return ToolResult(
            llm_response={
                "ok": False,
                "error": "invalid_date",
                "hint": "Ask for mm/dd/yyyy, for example 03/25/2026.",
            }
        )
    if context is not None:
        context.memory.set("incident_date", normalized)
    return ToolResult(llm_response={"ok": True, "incident_date": normalized})


@tool(description="Submit a new insurance claim for the current customer.")
async def submit_claim(
    policy_num: str,
    policy_name: str,
    claim_description: str,
    incident_date: str,
    additional_claim_info: str,
    incident_time: str = "",
    incident_location: str = "",
    context: ToolContext = None,
) -> ToolResult:
    """Submit a claim.

    Args:
        policy_num: Policy number selected for the claim.
        policy_name: Policy type (Car or Homeowner).
        claim_description: What happened.
        incident_date: Incident date in MM/DD/YYYY.
        additional_claim_info: Witnesses, police report, or other notes.
        incident_time: Time of incident (auto claims).
        incident_location: Location of incident (auto claims).
    """
    customer_id = customer_id_from_context(context)
    db = Database()

    policy = db.run_query(
        """
        SELECT policy_num, policy_type FROM policies
        WHERE customer_id = ? AND policy_num = ?
        """,
        (customer_id, policy_num),
        one_record=True,
    )
    if not policy:
        return ToolResult(
            llm_response={
                "ok": False,
                "error": "policy_not_found",
                "policy_num": policy_num,
            }
        )

    normalized_date = normalize_incident_date(incident_date) or incident_date
    # Demo parity with the source starter: always return claim number 12345.
    claim_id = "12345"
    today = datetime.now().strftime("%m/%d/%Y")

    db.cursor.execute(
        """
        INSERT OR REPLACE INTO claims
        (customer_id, claim_id, policy_num, claim_date, claim_status, inspection_date)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (customer_id, f"CLAIM{claim_id}", policy_num, today, 0, None),
    )
    db.commit()

    if context is not None:
        context.memory.set("claim_submitted", True)
        context.memory.set("submitted_claim_number", claim_id)
        context.memory.set("incident_date", normalized_date)

    return ToolResult(
        llm_response={
            "ok": True,
            "claim_number": claim_id,
            "policy_num": policy_num,
            "policy_name": policy_name,
            "claim_description": claim_description,
            "incident_date": normalized_date,
            "incident_time": incident_time,
            "incident_location": incident_location,
            "additional_claim_info": additional_claim_info,
            "message": "An adjuster will be assigned to your claim.",
        }
    )
