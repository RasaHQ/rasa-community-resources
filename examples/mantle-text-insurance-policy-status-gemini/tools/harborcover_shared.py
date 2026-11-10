"""Shared HarborCover tools, used by more than one skill.

The customer id always comes from project memory, which load_caller_profile
writes at session start. The model supplies only numbers and a loss
description; it never supplies a customer id, a fact or an outcome.
"""

from __future__ import annotations

from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult

from lib.harborcover import DEMO_CUSTOMER_ID, caller_profile, coverage_question


def session_customer_id(context: ToolContext | None) -> str:
    """The caller bound to this session, from trusted project memory."""
    if context is None:
        return DEMO_CUSTOMER_ID
    return context.memory.get("project.customer_id") or DEMO_CUSTOMER_ID


@tool(description="Load the identified caller's profile into project memory at session start.")
async def load_caller_profile(context: ToolContext = None) -> ToolResult:
    profile = caller_profile()
    if context is not None:
        context.memory.set("project.customer_id", profile["customer_id"])
        context.memory.set("project.customer_first_name", profile["first_name"])
        context.memory.set("project.policy_numbers", ", ".join(profile["policy_numbers"]))
        context.memory.set("project.claim_numbers", ", ".join(profile["claim_numbers"]))
    return ToolResult(llm_response={"ok": True, **profile})


@tool(
    description=(
        "Route a question about whether a particular loss or damage is covered "
        "to the HarborCover claims service. Use it whenever the caller asks if "
        "something is or will be covered and no coverage decision exists for "
        "that exact claim. Returns a reference and the next review step, never "
        "a yes or no."
    )
)
async def open_coverage_question(
    policy_number: str,
    loss_description: str,
    context: ToolContext = None,
) -> ToolResult:
    """Open a coverage question with the claims service.

    Args:
        policy_number: The caller's policy the loss falls under, for example HC-HO-440120.
        loss_description: The caller's own short description of the loss.
    """
    result = coverage_question(session_customer_id(context), policy_number, loss_description)
    return ToolResult(llm_response=result)
