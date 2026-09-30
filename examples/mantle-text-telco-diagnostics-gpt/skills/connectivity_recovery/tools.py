"""Recovery-step tools. The guard runs in lib.juniper, not in the prompt.

select_recovery_step resolves one operation on one device and writes the
selection to skill memory (never llm_settable), so the confirmation question
the engine asks is built from the tool's data. run_recovery_step is gated by
the engine's requires_confirmation, and lib.juniper checks independently, from
the conversation transcript, that the disruption boundary reached the customer
word for word and that they replied after it.
"""

from __future__ import annotations

from typing import Optional

from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult

from lib import juniper as jm


def network() -> jm.NetworkService:
    """This conversation's network state (the same object the shared tools use)."""
    try:
        from rasa.mantle.orchestration.turn_context import current_turn_context

        return jm.service_for(current_turn_context().sender_id)
    except Exception:
        return jm.service_for("offline")


def session_customer_id(context: Optional[ToolContext]) -> str:
    """The customer bound to this session, from trusted project memory."""
    if context is None:
        return jm.DEMO_CUSTOMER_ID
    return context.memory.get("project.customer_id") or jm.DEMO_CUSTOMER_ID


def transcript(context: Optional[ToolContext]) -> list[tuple[str, str]]:
    """The conversation's user and bot messages, in order, from the tracker."""
    if context is None:
        return []
    out: list[tuple[str, str]] = []
    for event in context.events:
        kind = getattr(event, "type_name", None)
        if kind in ("user", "bot"):
            out.append((kind, getattr(event, "text", None) or ""))
    return out


def _remember(context: Optional[ToolContext], result: dict) -> None:
    if context is None:
        return
    # A new selection, a blocked one or a cancel always replaces the old one,
    # so the engine can never ask about a stale step.
    selected = result.get("status") == "selected"
    context.memory.set("selected_step_ref", result.get("selection_ref", "") if selected else "")
    context.memory.set(
        "selected_step_label",
        f"{jm.load_data()['operations'][result['operation']]['label']} of the {result['service_label']} hub at {result['address']}"
        if selected else "",
    )
    context.memory.set("selected_step_boundary", result.get("disruption_boundary", "") if selected else "")


@tool(
    description=(
        "Choose one recovery step on one of the customer's services: operation "
        "reboot or factory_reset, exactly as the customer chose it. Sends nothing "
        "to the device. Returns a selection_ref and the disruption boundary, or "
        "blocked with a next_step."
    )
)
async def select_recovery_step(service_id: str, operation: str, context: ToolContext = None) -> ToolResult:
    """Select a recovery step.

    Args:
        service_id: The customer's service id, for example JM-FB-204988.
        operation: reboot or factory_reset, as the customer chose it.
    """
    user_texts = [text for kind, text in transcript(context) if kind == "user"]
    result = jm.select_recovery_step(network(), session_customer_id(context), service_id, operation, user_texts)
    _remember(context, result)
    return ToolResult(llm_response=result)


@tool(
    description=(
        "Send the selected recovery step to the device, identified by the "
        "selection_ref from select_recovery_step. The engine asks the customer "
        "to confirm the disruption first."
    )
)
async def run_recovery_step(selection_ref: str, context: ToolContext = None) -> ToolResult:
    """Run the selected recovery step.

    Args:
        selection_ref: The selection_ref from select_recovery_step, for example JM-SEL-1A2B3C4D.
    """
    result = jm.run_recovery_step(network(), session_customer_id(context), selection_ref, transcript(context))
    if context is not None and result.get("status") == "executed":
        context.memory.set("selected_step_ref", "")
    return ToolResult(llm_response=result)


@tool(
    description=(
        "Cancel the pending recovery step, for example when the customer changes "
        "their mind or someone else is using the connection. Nothing is sent to "
        "the device."
    )
)
async def cancel_recovery_step(context: ToolContext = None) -> ToolResult:
    result = jm.cancel_recovery_step(network())
    if context is not None:
        context.memory.set("selected_step_ref", "")
    return ToolResult(llm_response=result)
