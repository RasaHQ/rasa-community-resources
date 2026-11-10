"""The router restart helper's one tool.

OPERATIONS is the table the first check reads. It maps what the customer asked for to
the command that is sent. A restart must send REBOOT. No device is contacted in this
workshop: the tool only returns the command it would send.
"""

from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult

OPERATIONS = {"restart": "REBOOT"}


@tool(description="Restart the customer's router. Sends one restart command and nothing else.")
async def restart_router(context: ToolContext = None) -> ToolResult:
    command = OPERATIONS["restart"]
    return ToolResult(llm_response={"status": "sent", "command_sent": command})
