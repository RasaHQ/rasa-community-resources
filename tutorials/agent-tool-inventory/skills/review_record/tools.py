from rasa.mantle.tools.decorator import tool, ToolContext
from rasa.mantle.tools.result import ToolResult
@tool(description="Read an invented status.")
async def read_status(context: ToolContext) -> ToolResult:
    return ToolResult(llm_response={"status": "ready"})
