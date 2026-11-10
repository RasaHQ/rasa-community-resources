"""Claim-intake tools. The guard runs in lib.claims, not in the prompt.

The signed-in customer is project memory that only the session tool writes.
The draft and its read-back values are skill memory that only these tools
write (never ``llm_settable``), so the report the engine reads back for
confirmation is always the draft the tools hold. Each value is one short
field: Mantle cuts a memory value at 100 characters in the prompt without
saying so.

When ``lib.claims.TOOL_SENDS_RECEIPT`` is on, ``submit_claim_report`` sends
the customer its outcome itself through ``ToolContext.send``: the claim
reference and the material received, or "not filed yet". The model's reply
comes after it, whatever the model does.
"""

from __future__ import annotations

from typing import Optional

from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult

from lib import claims as hc
from lib.conversation import conversation_from_events

CUSTOMER_KEY = "project.customer_id"


def _conversation_id() -> str:
    try:
        from rasa.mantle.orchestration.turn_context import current_turn_context

        return current_turn_context().sender_id
    except Exception:
        return "offline"


def _service() -> hc.ClaimsIntake:
    return hc.service_for(_conversation_id())


def _customer(context: Optional[ToolContext]) -> Optional[str]:
    return (context.memory.get(CUSTOMER_KEY) if context is not None else None) or None


def _conversation(context: Optional[ToolContext]) -> hc.Conversation:
    return conversation_from_events(context.events) if context is not None else hc.Conversation()


def _write_memory(context: Optional[ToolContext], service: hc.ClaimsIntake, draft: Optional[hc.Draft]) -> None:
    if context is None or draft is None:
        return
    for key, value in hc.memory_values(service, draft).items():
        context.memory.set(key, value)


async def _send_receipt(context: Optional[ToolContext], tool_name: str, result: dict) -> None:
    text = hc.customer_receipt(tool_name, result) if hc.TOOL_SENDS_RECEIPT else None
    if text and context is not None:
        await context.send(text)


@tool(
    description=(
        "Open a draft claim report on one of the signed-in customer's policies from what they told you: the "
        "policy, the type of loss, the date of loss, a one-line summary in their words and the full details. "
        "A draft is not a filed claim. Also reads the files they attached in this chat."
    )
)
async def start_claim_draft(
    policy_number: str,
    loss_type: str,
    loss_date: str,
    loss_summary: str,
    loss_details: Optional[str] = None,
    loss_location: Optional[str] = None,
    context: ToolContext = None,
) -> ToolResult:
    """Open a draft report.

    Args:
        policy_number: The customer's policy, for example HC-HO-552104.
        loss_type: water_damage, storm_damage, accidental_damage, theft or collision.
        loss_date: The date of loss the customer gave, as YYYY-MM-DD.
        loss_summary: What happened in one line of the customer's words, at most 80 characters.
        loss_details: Everything else the customer said about the loss.
        loss_location: Where it happened, if not the insured address.
    """
    service = _service()
    result, draft = hc.start_claim_draft(
        service, _customer(context), _conversation_id(), _conversation(context),
        policy_number, loss_type, loss_date, loss_summary, loss_details, loss_location,
    )
    _write_memory(context, service, draft)
    return ToolResult(llm_response=result)


@tool(
    description=(
        "Change a draft that has not been submitted: the date of loss, the type, the summary, the details or "
        "the location. Any change makes a new version that the customer must confirm again."
    )
)
async def update_claim_draft(
    draft_id: str,
    loss_date: Optional[str] = None,
    loss_type: Optional[str] = None,
    loss_summary: Optional[str] = None,
    loss_details: Optional[str] = None,
    loss_location: Optional[str] = None,
    context: ToolContext = None,
) -> ToolResult:
    """Change a draft.

    Args:
        draft_id: The draft_id from start_claim_draft, for example HC-FD-3A9C1.
        loss_date: A corrected date of loss, as YYYY-MM-DD.
        loss_type: A corrected type of loss.
        loss_summary: A corrected one-line summary, at most 80 characters.
        loss_details: Corrected or added details.
        loss_location: A corrected location.
    """
    service = _service()
    result, draft = hc.update_claim_draft(
        service, _customer(context), _conversation(context), draft_id,
        loss_date, loss_type, loss_summary, loss_details, loss_location,
    )
    _write_memory(context, service, draft)
    return ToolResult(llm_response=result)


@tool(
    description=(
        "Read the state of every file the customer attached in this chat from the attachment service and link "
        "them to the draft: received, failed, still scanning, or never received. Pass exclude with file names the "
        "customer asked to leave out. Call it again after new attachments or when a file was still scanning."
    )
)
async def check_attachments(
    draft_id: str,
    exclude: Optional[str] = None,
    context: ToolContext = None,
) -> ToolResult:
    """Check the draft's attachments.

    Args:
        draft_id: The draft_id from start_claim_draft.
        exclude: Comma-separated file names the customer asked to leave out, for example glazier-quote.pdf.
    """
    service = _service()
    names = [n.strip() for n in (exclude or "").split(",") if n.strip()]
    result, draft = hc.check_attachments(service, _customer(context), _conversation(context), draft_id, names)
    _write_memory(context, service, draft)
    return ToolResult(llm_response=result)


@tool(
    description=(
        "Submit the draft report to HarborCover's claims system. The engine reads the report back and asks the "
        "customer to confirm first. Returns a claim-intake reference only when the claims system acknowledges "
        "the submission; otherwise the claim is pending and not filed."
    )
)
async def submit_claim_report(draft_id: str, context: ToolContext = None) -> ToolResult:
    """Submit one confirmed draft.

    Args:
        draft_id: The draft_id from start_claim_draft.
    """
    memory = {key: (context.memory.get(key) if context is not None else None) or None for key in hc.MEMORY_KEYS}
    result = hc.submit_claim_report(_service(), _customer(context), memory, _conversation(context), draft_id)
    await _send_receipt(context, "submit_claim_report", result)
    return ToolResult(llm_response=result)
