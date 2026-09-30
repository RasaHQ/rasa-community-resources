"""Roadside dispatch tools. The guard runs in lib.roadside, not in the prompt.

The matched policy and the pending draft (its version tag and the vehicle,
place and service the engine reads back) are skill memory that only these
tools write (never ``llm_settable``), so the place the caller confirms is
always the draft the tools hold. The model passes a policy number and
surname, a vehicle reference, a service word, the caller's description of
where the vehicle is, a provider name the caller asked for, and references
copied from tool results.

When ``lib.roadside.TOOL_SENDS_RECEIPT`` is on, the tools send the caller
each outcome themselves through ``ToolContext.send``: the assistance
reference with the provider's answer, a refusal, or the desk reference. It is
spoken whatever the model does next.
"""

from __future__ import annotations

from typing import Optional

from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult

from lib import roadside as hc


def _conversation_id() -> str:
    try:
        from rasa.mantle.orchestration.turn_context import current_turn_context

        return current_turn_context().sender_id
    except Exception:
        return "offline"


def _service() -> hc.RoadsideService:
    return hc.service_for(_conversation_id())


def _memory(context: Optional[ToolContext]) -> dict:
    return {key: (context.memory.get(key) if context is not None else None) or None for key in hc.MEMORY_KEYS}


def _conversation(context: Optional[ToolContext]) -> hc.Conversation:
    return hc.conversation_from_events(context.events) if context is not None else hc.Conversation()


def _write_draft(context: Optional[ToolContext], service: hc.RoadsideService, draft: Optional[hc.Draft]) -> None:
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
        "Find the caller's HarborCover auto policy from the six digits of its policy number and the policyholder's "
        "last name. Returns the vehicles on the policy. The address on the policy is never the breakdown location."
    )
)
async def find_policy(policy_number: str, last_name: str, context: ToolContext = None) -> ToolResult:
    """Match the caller to a policy.

    Args:
        policy_number: The policy number as the caller said it, for example HC-AU-440218 or 4 4 0 2 1 8.
        last_name: The policyholder's last name.
    """
    result = hc.find_policy(_service(), policy_number, last_name)
    if context is not None:
        context.memory.set("policy_number", result.get("policy_number") or "")
        for key, value in hc.memory_values(_service(), None).items():
            context.memory.set(key, value)
    return ToolResult(llm_response=result)


@tool(
    description=(
        "Open a roadside dispatch draft for one vehicle on the matched policy: the help it needs and where the "
        "vehicle is right now, in the caller's words. Sends nothing. Name a provider only if the caller asked for "
        "one; it is used only if it can do the job."
    )
)
async def start_dispatch_draft(
    vehicle_ref: str,
    service_needed: str,
    location: str,
    preferred_provider: Optional[str] = None,
    context: ToolContext = None,
) -> ToolResult:
    """Open a draft.

    Args:
        vehicle_ref: The vehicle_ref from find_policy, for example VEH-4402-1.
        service_needed: tow, jump_start, flat_tyre, lockout or fuel.
        location: Where the vehicle is now, as the caller said it: road and direction with exit or mile marker, a street number and street, or a business.
        preferred_provider: A roadside company the caller asked for by name, if any.
    """
    service = _service()
    result, draft = hc.start_dispatch_draft(service, _memory(context).get("policy_number"), vehicle_ref,
                                            service_needed, location, preferred_provider)
    _write_draft(context, service, draft)
    await _send_receipt(context, "start_dispatch_draft", result)
    return ToolResult(llm_response=result)


@tool(
    description=(
        "Change a draft that has not been dispatched: where the vehicle is, the help it needs, the vehicle, or a "
        "provider the caller asked for. Any change makes a new version the caller must confirm."
    )
)
async def update_dispatch_draft(
    draft_id: str,
    location: Optional[str] = None,
    service_needed: Optional[str] = None,
    vehicle_ref: Optional[str] = None,
    preferred_provider: Optional[str] = None,
    context: ToolContext = None,
) -> ToolResult:
    """Change a draft.

    Args:
        draft_id: The draft_id from start_dispatch_draft, for example HC-RD-418266.
        location: The corrected place, in the caller's words.
        service_needed: The corrected help: tow, jump_start, flat_tyre, lockout or fuel.
        vehicle_ref: Another vehicle_ref from find_policy.
        preferred_provider: A roadside company the caller asked for by name.
    """
    service = _service()
    result, draft = hc.update_dispatch_draft(service, draft_id, location, service_needed, vehicle_ref,
                                             preferred_provider)
    _write_draft(context, service, draft)
    await _send_receipt(context, "update_dispatch_draft", result)
    return ToolResult(llm_response=result)


@tool(
    description=(
        "Send the drafted job to a suitable roadside provider. The engine first reads the place back and asks the "
        "caller to confirm where the vehicle is now. Returns an assistance reference and the provider's answer: "
        "accepted, not yet accepted, or declined."
    )
)
async def request_dispatch(draft_id: str, context: ToolContext = None) -> ToolResult:
    """Dispatch one confirmed draft.

    Args:
        draft_id: The draft_id from start_dispatch_draft.
    """
    result = hc.request_dispatch(_service(), draft_id, _memory(context), _conversation(context))
    await _send_receipt(context, "request_dispatch", result)
    return ToolResult(llm_response=result)


@tool(
    description=(
        "After a provider declined, send the same job, with the same assistance reference and the place the caller "
        "already confirmed, to the next suitable provider."
    )
)
async def request_next_provider(assistance_ref: str, context: ToolContext = None) -> ToolResult:
    """Try the next suitable provider.

    Args:
        assistance_ref: The assistance_ref from request_dispatch, for example HC-RSA-482173.
    """
    result = hc.request_next_provider(_service(), assistance_ref)
    await _send_receipt(context, "request_next_provider", result)
    return ToolResult(llm_response=result)


@tool(
    description=(
        "Read the provider's answer to a dispatched job again: accepted with or without an arrival estimate, or not "
        "yet accepted. The caller saying someone is coming is not an answer."
    )
)
async def check_dispatch(assistance_ref: str, context: ToolContext = None) -> ToolResult:
    """Check a dispatched job.

    Args:
        assistance_ref: The assistance_ref from request_dispatch.
    """
    result = hc.check_dispatch(_service(), assistance_ref)
    await _send_receipt(context, "check_dispatch", result)
    return ToolResult(llm_response=result)


@tool(
    description=(
        "Pass the job to the HarborCover dispatch desk when no suitable provider can take it or the caller needs a "
        "person. Keeps any draft or assistance reference. Returns a desk reference."
    )
)
async def route_dispatch_desk(
    reason: str,
    draft_id: Optional[str] = None,
    assistance_ref: Optional[str] = None,
    context: ToolContext = None,
) -> ToolResult:
    """Route to the dispatch desk.

    Args:
        reason: One short sentence, for example no heavy-duty tow covers Easton Falls.
        draft_id: The draft_id, if there is one.
        assistance_ref: The assistance_ref, if the job was dispatched.
    """
    result = hc.route_dispatch_desk(_service(), reason, draft_id, assistance_ref)
    await _send_receipt(context, "route_dispatch_desk", result)
    return ToolResult(llm_response=result)
