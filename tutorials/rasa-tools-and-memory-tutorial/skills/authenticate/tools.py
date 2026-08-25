"""LOCAL tools for the authenticate skill.

Local because nothing outside this skill should ever call them: checking a
passphrase is this skill's workflow, not a shared utility. Files in a skill's
own folder are auto-discovered — no import_tools entry, no registration.

Porting this skill to another agent means copying this folder. That is the
whole point of keeping the tool here.
"""

from __future__ import annotations

from rasa.calm_v2.tools.decorator import ToolContext, tool
from rasa.calm_v2.tools.result import ToolResult

from lib.directory import customer_by_passphrase


@tool(description="Check the caller's passphrase and sign them in if it matches.")
async def verify_passphrase(passphrase: str, context: ToolContext = None) -> ToolResult:
    """Verify the caller's passphrase.

    Args:
        passphrase: The secret word the caller gives to prove identity.
    """
    customer = customer_by_passphrase(passphrase)

    if customer is None:
        if context is not None:
            attempts = context.memory.get("passphrase_attempts") or 0
            context.memory.set("passphrase_attempts", int(attempts) + 1)
        return ToolResult(
            llm_response={"ok": False, "error": "passphrase_incorrect"}
        )

    # Writing to project memory is what lets later skills skip this work.
    if context is not None:
        # Bare names on write: the slice resolves them against this skill, then
        # the project. A qualified "project.x" is valid on get(), not on set().
        context.memory.set("customer_id", customer["customer_id"])
        context.memory.set("authenticated", True)
        context.memory.set("verification_method", "passphrase")

    return ToolResult(
        llm_response={
            "ok": True,
            "customer_id": customer["customer_id"],
            "name": customer["name"],
        }
    )
