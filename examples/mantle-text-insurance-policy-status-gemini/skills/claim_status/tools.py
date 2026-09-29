"""Claim status tools. The guard runs in lib.harborcover, not in the prompt."""

from __future__ import annotations

from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult

from lib.harborcover import DEMO_CUSTOMER_ID, case_team_callback, claim_status


def _customer(context: ToolContext | None) -> str:
    return (
        context.memory.get("project.customer_id") if context is not None else None
    ) or DEMO_CUSTOMER_ID


@tool(
    description=(
        "Look up the recorded stage of one of the caller's claims. Returns the "
        "stage, timestamps, next review step and a status reference. A coverage "
        "decision is present only when decision_type is coverage_decision."
    )
)
async def get_claim_status(claim_number: str, context: ToolContext = None) -> ToolResult:
    """Look up a claim's status.

    Args:
        claim_number: The claim number, for example CLM-24-0871.
    """
    return ToolResult(llm_response=claim_status(_customer(context), claim_number))


@tool(
    description=(
        "Ask the claims case team to call the caller back about a claim whose "
        "current status cannot be given. Use after a blocked claim status."
    )
)
async def request_case_team_callback(claim_number: str, context: ToolContext = None) -> ToolResult:
    """Request a case-team callback.

    Args:
        claim_number: The claim the callback is about.
    """
    return ToolResult(llm_response=case_team_callback(_customer(context), claim_number))
