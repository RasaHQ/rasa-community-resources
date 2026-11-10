"""Policy status tool. The guard runs in lib.harborcover, not in the prompt."""

from __future__ import annotations

from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult

from lib.harborcover import DEMO_CUSTOMER_ID, policy_status


@tool(
    description=(
        "Look up the recorded state and effective dates of one of the caller's "
        "policies. The result is a policy status, never a coverage decision."
    )
)
async def get_policy_status(policy_number: str, context: ToolContext = None) -> ToolResult:
    """Look up a policy's status.

    Args:
        policy_number: The policy number, for example HC-HO-440120.
    """
    customer_id = (
        context.memory.get("project.customer_id") if context is not None else None
    ) or DEMO_CUSTOMER_ID
    return ToolResult(llm_response=policy_status(customer_id, policy_number))
