from rasa.mantle.tools.decorator import tool, ToolContext
from rasa.mantle.tools.result import ToolResult
@tool(description="Record an invented review result.")
async def record_review(context: ToolContext) -> ToolResult:
    return ToolResult(llm_response={"status": "fixture_only"})
@tool(description="Unimported shared fixture tool.")
async def unused_shared(context: ToolContext) -> ToolResult:
    return ToolResult(llm_response={"status": "not_exposed"})
