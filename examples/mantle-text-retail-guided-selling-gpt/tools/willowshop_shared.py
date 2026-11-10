"""Willow Shop tools, shared by the guided-selling and fit-check skills.

The guard runs in lib.willowshop, not in the prompt. Each tool reads the
shopper's own messages and earlier tool results from the conversation's
events, so the facts the contract checks never come from the model. The model
supplies only a device model name, a product id, a category and a question.
"""

from __future__ import annotations

from typing import Optional

from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult
from rasa.shared.core.events import ToolExecuted, UserUttered

from lib import willowshop as ws


def _user_texts(context: Optional[ToolContext]) -> list[str]:
    if context is None:
        return []
    return [e.text or "" for e in context.events if isinstance(e, UserUttered)]


def _requirements(context: Optional[ToolContext]) -> Optional[dict]:
    if context is None:
        return None
    return ws.current_requirements(
        [(e.tool_name, e.result) for e in context.events if isinstance(e, ToolExecuted)]
    )


@tool(
    description=(
        "Record the device the shopper says they have, before any recommendation "
        "or fit check. Pass the model exactly as the shopper wrote it. Call it "
        "again whenever the shopper names a different device. Set uses_case to "
        "true only when the shopper says they keep the phone in a case."
    )
)
async def record_requirements(
    device_model: str,
    uses_case: Optional[bool] = None,
    context: ToolContext = None,
) -> ToolResult:
    """Record the shopper's device.

    Args:
        device_model: The device model in the shopper's words, for example Lumen 7 Pro.
        uses_case: True when the shopper said they keep the phone in a case.
    """
    return ToolResult(llm_response=ws.record_requirements(device_model, _user_texts(context), uses_case))


@tool(
    description=(
        "List Willow Shop products in one category: charging_dock, case, cable, "
        "wireless_charger or car_mount. Returns ids, names and prices only; "
        "names say nothing about fit."
    )
)
async def search_catalogue(category: str, context: ToolContext = None) -> ToolResult:
    """List products in a category.

    Args:
        category: One of charging_dock, case, cable, wireless_charger, car_mount.
    """
    return ToolResult(llm_response=ws.search_catalogue(category))


@tool(
    description=(
        "Check one product against the shopper's recorded device and, when its "
        "fit is established by catalogue sources and its stock is current, "
        "return a recommendation with the supporting attributes. Use it for "
        "every recommendation and every 'does this fit' question."
    )
)
async def recommend_product(product_id: str, context: ToolContext = None) -> ToolResult:
    """Recommend a product for the recorded device.

    Args:
        product_id: The catalogue id, for example WS-DK-L7.
    """
    return ToolResult(
        llm_response=ws.recommend_product(product_id, _requirements(context), _user_texts(context))
    )


@tool(
    description=(
        "Ask a Willow Shop product specialist to confirm a fit the catalogue "
        "cannot establish. Returns a reference; never a yes or no."
    )
)
async def request_specialist(product_id: str, question: str, context: ToolContext = None) -> ToolResult:
    """Route an unknown fit to a product specialist.

    Args:
        product_id: The product the question is about, for example WS-CM-GRIP.
        question: The unresolved fit question in one sentence.
    """
    return ToolResult(llm_response=ws.request_specialist(product_id, question, _requirements(context)))
