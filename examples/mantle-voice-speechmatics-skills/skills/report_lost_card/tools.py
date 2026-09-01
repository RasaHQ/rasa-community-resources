"""Tools local to the report_lost_card skill (auto-discovered)."""

from __future__ import annotations

from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult

from lib.bank import CARDS, normalise_digits


@tool(
    description=(
        "Block a card by its last four digits. Accepts the digits exactly as "
        "heard, including spaces."
    )
)
async def block_card(card_last_four: str, context: ToolContext = None) -> ToolResult:
    """Block a card, normalising spoken digits first.

    Args:
        card_last_four: Last four digits as transcribed — "4532", "4 5 3 2".
    """
    digits = normalise_digits(card_last_four)

    if len(digits) != 4:
        # Deliberately not a guess. Blocking the wrong card is worse than
        # asking again, so an ambiguous transcript fails loudly.
        if context is not None:
            context.memory.set("card_blocked", False)
        return ToolResult(
            llm_response={
                "ok": False,
                "error": "need_four_digits",
                "heard": card_last_four,
                "digits_found": digits,
                "hint": "Ask the caller to say the four digits again, one at a time.",
            }
        )

    card = CARDS.get(digits)
    if card is None:
        if context is not None:
            context.memory.set("card_blocked", False)
        return ToolResult(
            llm_response={
                "ok": False,
                "error": "card_not_found",
                "card_last_four": digits,
                "hint": "No card on this account ends in those digits.",
            }
        )

    card["status"] = "blocked"
    if context is not None:
        context.memory.set("card_last_four", digits)
        context.memory.set("card_blocked", True)

    return ToolResult(
        llm_response={
            "ok": True,
            "card_last_four": digits,
            "card_type": card["type"],
            "status": "blocked",
            "replacement_days": "5 to 7 business days",
        }
    )
