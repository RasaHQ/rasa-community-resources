"""Shared Juniper Mobile tools, used by more than one skill. All read-only.

The customer id always comes from project memory, which load_customer_profile
writes at session start. The model supplies only a service id and, for a
technician visit, a one-line reason. Network state is kept per conversation
in lib.juniper, so every scripted conversation starts from the same fixture.
"""

from __future__ import annotations

from typing import Optional

from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult

from lib import juniper as jm

CUSTOMER_KEY = "project.customer_id"


def conversation_id() -> str:
    try:
        from rasa.mantle.orchestration.turn_context import current_turn_context

        return current_turn_context().sender_id
    except Exception:
        return "offline"


def network() -> jm.NetworkService:
    return jm.service_for(conversation_id())


def session_customer_id(context: Optional[ToolContext]) -> str:
    """The customer bound to this session, from trusted project memory."""
    if context is None:
        return jm.DEMO_CUSTOMER_ID
    return context.memory.get(CUSTOMER_KEY) or jm.DEMO_CUSTOMER_ID


@tool(description="Load the identified customer's profile and services into project memory at session start.")
async def load_customer_profile(context: ToolContext = None) -> ToolResult:
    profile = jm.customer_profile()
    if context is not None and not context.memory.get(CUSTOMER_KEY):
        # Project memory is write-once on this engine; write each field once.
        context.memory.set(CUSTOMER_KEY, profile["customer_id"])
        context.memory.set("project.customer_first_name", profile["first_name"])
        # One field per service. Mantle renders each memory value into the
        # prompt cut at 100 characters (rasa/mantle/prompts/memory_lines.py,
        # MAX_MEMORY_VALUE_LENGTH). The first version joined all three
        # services into one 170-character field, the model saw two and a
        # "[truncated]" marker, and told the customer they had two services.
        for key, line in jm.service_memory_lines(profile).items():
            context.memory.set(f"project.{key}", line)
    return ToolResult(llm_response={"ok": True, **profile})


@tool(
    description=(
        "Check whether there is a known network outage in the area of one of the "
        "customer's services. Read-only. Returns outage (with incident and "
        "estimated restore time), clear, or unknown when the outage feed is down."
    )
)
async def check_area_outage(service_id: str, context: ToolContext = None) -> ToolResult:
    """Check the area-outage status.

    Args:
        service_id: The customer's service id, for example JM-FB-204988.
    """
    return ToolResult(llm_response=jm.check_area_outage(network(), session_customer_id(context), service_id))


@tool(
    description=(
        "Run read-only diagnostics on one of the customer's services: signal, "
        "internet session and Wi-Fi as the hub reports them. Sends no command to "
        "the device and interrupts nothing."
    )
)
async def run_line_diagnostics(service_id: str, context: ToolContext = None) -> ToolResult:
    """Run read-only line diagnostics.

    Args:
        service_id: The customer's service id, for example JM-FB-204988.
    """
    return ToolResult(llm_response=jm.run_line_diagnostics(network(), session_customer_id(context), service_id))


@tool(
    description=(
        "Request a technician visit for one of the customer's services. Use when "
        "the outage status is unknown, or when diagnostics show a fault the "
        "customer's device cannot fix. Changes nothing on the device."
    )
)
async def request_technician_visit(service_id: str, reason: str, context: ToolContext = None) -> ToolResult:
    """Request a technician visit.

    Args:
        service_id: The customer's service id.
        reason: One short sentence, for example outage status unknown and no mobile signal.
    """
    return ToolResult(
        llm_response=jm.request_technician_visit(network(), session_customer_id(context), service_id, reason)
    )
