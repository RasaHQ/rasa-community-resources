"""Public synthetic records; no account operation or provider request."""

from rasa.mantle.tools.decorator import tool
from rasa.mantle.tools.result import ToolResult

RECORDS = {
    "north": {
        "reference": "JM-N-101",
        "area": "north",
        "observation": "Synthetic planned maintenance from 14:00 to 16:00 UTC.",
    },
    "central": {
        "reference": "JM-C-102",
        "area": "central",
        "observation": "Synthetic public record: no planned maintenance listed.",
    },
}


@tool(
    description="Inspect the public synthetic north or central area record. Supply the chosen area; ask for a supported choice when missing."
)
async def inspect_public_area(area: str) -> ToolResult:
    if not isinstance(area, str):
        return ToolResult(
            llm_response={"status": "needs_area", "supported": ["north", "central"]}
        )
    record = RECORDS.get(area.strip().casefold())
    if record is None:
        return ToolResult(
            llm_response={"status": "needs_area", "supported": ["north", "central"]}
        )
    return ToolResult(llm_response={"status": "ready", **record})
