"""Tools local to the block_card skill (auto-discovered, no import_tools)."""

from __future__ import annotations

from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult

from lib.database import Database, get_user_id, mask_card, username_from_context


@tool(description="List the customer's active bank cards.")
async def list_cards(context: ToolContext = None) -> ToolResult:
    username = username_from_context(context)
    db = Database()
    user_id = get_user_id(db, username)
    if user_id is None:
        return ToolResult(llm_response={"ok": False, "error": "customer_not_found"})

    rows = db.run_query(
        "SELECT number, type, status FROM cards WHERE user_id = ?",
        (user_id,),
        one_record=False,
    )
    cards = [
        {
            "card_number": number,
            "masked": mask_card(number),
            "type": card_type,
            "status": status,
        }
        for number, card_type, status in rows or []
    ]
    if context is not None:
        context.memory.set("cards_loaded", True)
    return ToolResult(llm_response={"ok": True, "cards": cards, "card_count": len(cards)})


@tool(description="Block or freeze a card so it cannot be used.")
async def block_card(card_number: str, context: ToolContext = None) -> ToolResult:
    """Block a card.

    Args:
        card_number: Full card number to block.
    """
    username = username_from_context(context)
    db = Database()
    user_id = get_user_id(db, username)
    if user_id is None:
        return ToolResult(llm_response={"ok": False, "error": "customer_not_found"})

    db.cursor.execute(
        """
        UPDATE cards
        SET status = 'inactive', updated_at = CURRENT_TIMESTAMP
        WHERE number = ? AND user_id = ?
        """,
        (card_number, user_id),
    )
    updated = db.cursor.rowcount
    db.commit()
    if updated == 0:
        return ToolResult(
            llm_response={"ok": False, "error": "card_not_found", "card_number": card_number}
        )

    if context is not None:
        context.memory.set("card_blocked", True)
        context.memory.set("selected_card_id", card_number)
        context.memory.set("selected_card_label", mask_card(card_number))

    return ToolResult(
        llm_response={
            "ok": True,
            "card_number": card_number,
            "masked": mask_card(card_number),
            "status": "inactive",
        }
    )


@tool(description="Request a replacement card to be shipped to the customer's address.")
async def order_replacement_card(
    card_number: str, shipping: str = "standard", context: ToolContext = None
) -> ToolResult:
    """Order a replacement card.

    Args:
        card_number: Card being replaced.
        shipping: standard or express.
    """
    username = username_from_context(context)
    db = Database()
    row = db.run_query(
        "SELECT address FROM users WHERE name = ?", (username,), one_record=True
    )
    address = row[0] if row else "address on file"
    reference = f"CARD-{card_number[-4:]}-{shipping[:3].upper()}"
    if context is not None:
        context.memory.set("replacement_ordered", True)
        context.memory.set("shipping_type", shipping)
    return ToolResult(
        llm_response={
            "ok": True,
            "reference": reference,
            "shipping": shipping,
            "ship_to": address,
            "masked_card": mask_card(card_number),
        }
    )
