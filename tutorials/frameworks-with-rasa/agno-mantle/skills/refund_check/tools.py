from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult
from shop_adviser.refund_policy import assess_refund
from shop_adviser.return_records import find_return
from shop_adviser.scope_binding import resolve_demo_scope


@tool(description="Check a fictional Willow Shop return using its recorded payment and inspection. Supply the order reference only. Returns a read-only offer, missing-inspection status or need for staff review; issues no payment and contacts nobody.")
async def check_return(order_ref: str, context: ToolContext = None) -> ToolResult:
    from rasa.mantle.orchestration.turn_context import current_turn_context

    scope = resolve_demo_scope(current_turn_context().sender_id)
    if scope is None:
        return ToolResult(llm_response={"status": "unknown_demo_sender"})
    return ToolResult(llm_response=assess_refund(find_return(order_ref), scope.user_id))
