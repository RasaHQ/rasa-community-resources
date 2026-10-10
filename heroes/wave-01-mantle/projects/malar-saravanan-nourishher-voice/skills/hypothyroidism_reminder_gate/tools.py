"""Hypothyroidism-reminder-gate skill tools — local to skills/hypothyroidism_reminder_gate/.

This gate exists because a skill's `utter: on: activate / when:` verbatim trigger did not
fire in live testing (Bug 7, see README.md "Known open issues"), and neither did an explicit
"call this tool first" instruction inside an ordinary prose skill — the model simply chose
not to call it. This gate skill has no prose at all, only an `:::ordered_block`, which makes
its `execute_tool` step the flow's deterministic first step (engine-executed on activation,
no LLM discretion) rather than something the LLM decides whether to do.
"""

from __future__ import annotations

from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult

LEVOTHYROXINE_TIMING_REMINDER = (
    "Quick reminder on your levothyroxine: take it on an empty stomach, "
    "first thing, with plain water. Wait at least four hours before "
    "calcium or iron supplements, and before high-fiber or soy foods — "
    "they can reduce how much your body absorbs."
)


@tool(description="Send the levothyroxine timing safety reminder verbatim, once per session.")
async def send_levothyroxine_reminder_if_needed(context: ToolContext = None) -> ToolResult:
    """Send the levothyroxine timing reminder verbatim and mark it sent at project scope."""
    if context is None:
        return ToolResult(llm_response={"sent": False})

    await context.send(LEVOTHYROXINE_TIMING_REMINDER)
    context.memory.set("levothyroxine_reminder_sent", True)
    return ToolResult(llm_response={"sent": True})
