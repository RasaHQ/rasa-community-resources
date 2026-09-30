"""Session tool: bind the signed-in Horizon Travel traveller at session start.

The voice assistant runs inside the Horizon Travel app and website for a
signed-in traveller, so the session, not the caller's words, says whose
bookings these are. The traveller id always comes from project memory, which
only this tool writes. The model never supplies a traveller id, a contract
fact or a change outcome.
"""

from __future__ import annotations

from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult

from lib import journeys as hj


@tool(description="Load the signed-in traveller's profile into project memory at session start.")
async def load_session_traveller(context: ToolContext = None) -> ToolResult:
    traveller = hj.load_data()["travellers"][hj.SESSION_TRAVELLER_ID]
    if context is not None and not context.memory.get("project.traveller_id"):
        # Project memory is write-once on the pinned engine: set it once only.
        context.memory.set("project.traveller_id", hj.SESSION_TRAVELLER_ID)
        context.memory.set("project.traveller_first_name", traveller["first_name"])
    return ToolResult(llm_response={"ok": True, "first_name": traveller["first_name"],
                                    "today": hj.AS_OF.date().isoformat()})
