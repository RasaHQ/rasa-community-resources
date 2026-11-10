from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult
from lib.actions import handoff


@tool(description="Return a demo handoff receipt. Does not contact staff or create a real queue item.")
async def record_demo_handoff(context: ToolContext = None) -> ToolResult:
    return ToolResult(llm_response=handoff())
