"""A simulated local recording; no file, credential or external service access."""
from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult


@tool(description="Simulate recording a fictional value locally. Creates no real staff record.")
async def record_local_canary(value: str, context: ToolContext = None) -> ToolResult:
    return ToolResult(llm_response={"status": "simulated_recording", "value": value})
