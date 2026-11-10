"""HarborCover tools shared by the claim skills: session binding, submission status, intake team.

The chat runs for a signed-in policyholder, so the session, not the customer's
words, says whose policies these are. The customer id always comes from
project memory, which only ``load_session_customer`` writes. The guard runs in
lib.claims, not in the prompt; the model never supplies a customer id, a
contract fact or an outcome.
"""

from __future__ import annotations

from typing import Optional

from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult

from lib import claims as hc

CUSTOMER_KEY = "project.customer_id"


def conversation_id() -> str:
    try:
        from rasa.mantle.orchestration.turn_context import current_turn_context

        return current_turn_context().sender_id
    except Exception:
        return "offline"


def service() -> hc.ClaimsIntake:
    return hc.service_for(conversation_id())


def session_customer_id(context: Optional[ToolContext]) -> Optional[str]:
    return (context.memory.get(CUSTOMER_KEY) if context is not None else None) or None


async def send_receipt(context: Optional[ToolContext], tool_name: str, result: dict) -> None:
    text = hc.customer_receipt(tool_name, result) if hc.TOOL_SENDS_RECEIPT else None
    if text and context is not None:
        await context.send(text)


@tool(description="Load the signed-in policyholder's profile into project memory at session start.")
async def load_session_customer(context: ToolContext = None) -> ToolResult:
    profile = hc.session_profile()
    if context is not None and not context.memory.get(CUSTOMER_KEY):
        # Project memory is write-once on the pinned engine: set it once only.
        # Each value is one short field (Mantle cuts memory values at 100
        # characters in the prompt; see lib.claims.MEMORY_VALUE_LIMIT).
        context.memory.set(CUSTOMER_KEY, profile["customer_id"])
        context.memory.set("project.customer_first_name", profile["first_name"])
        context.memory.set("project.policy_list", profile["policy_list"])
    public = {k: v for k, v in profile.items() if k not in ("customer_id", "policy_list")}
    return ToolResult(llm_response={"ok": True, **public})


@tool(
    description=(
        "Look up a submitted report or an existing claim: by draft_id (HC-FD-...) or claim-intake reference "
        "(HC-CLI-...). After a submission that was not acknowledged, this asks the claims system about the same "
        "draft. Never submits anything."
    )
)
async def check_claim_submission(reference: str, context: ToolContext = None) -> ToolResult:
    """Look up a submission or claim.

    Args:
        reference: A draft_id such as HC-FD-3A9C1 or a claim-intake reference such as HC-CLI-40718.
    """
    result = hc.check_claim_submission(service(), session_customer_id(context), reference)
    await send_receipt(context, "check_claim_submission", result)
    return ToolResult(llm_response=result)


@tool(
    description=(
        "Hand a draft whose submission the claims system cannot confirm, or a claim question the tools cannot "
        "answer, to the claims intake team. Returns a desk reference; it files nothing and decides nothing."
    )
)
async def route_claims_intake(reference: str, reason: str, context: ToolContext = None) -> ToolResult:
    """Route to the claims intake team.

    Args:
        reference: The draft_id (HC-FD-...) or claim-intake reference (HC-CLI-...).
        reason: One short sentence, for example claims system cannot confirm the submission.
    """
    result = hc.route_claims_intake(service(), session_customer_id(context), reference, reason)
    await send_receipt(context, "route_claims_intake", result)
    return ToolResult(llm_response=result)
