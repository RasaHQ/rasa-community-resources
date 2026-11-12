"""Shared nutrition-lookup tools — used by every condition skill.

Shared here (not skill-local) because hypothyroidism_nutrition,
pcos_nutrition, diabetes_nutrition, and fertility_nutrition all call it.
"""

from __future__ import annotations

from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult

from lib.usda_client import USDALookupError, search_food


@tool(
    description=(
        "Look up real macro (calories, protein, fat, carbs, fiber, sugar) and "
        "micro (sodium, potassium, calcium, iron, zinc, magnesium, iodine, "
        "selenium, folate, vitamin D, vitamin B12) nutrients for a food from "
        "USDA FoodData Central, each with its %daily-value. Values are per "
        "100 g — always state that basis and the actual quantity eaten when "
        "presenting numbers."
    )
)
async def get_food_nutrient_info(food_query: str, context: ToolContext = None) -> ToolResult:
    """Look up macro/micro nutrient data (with %DV) for a food, per 100 g.

    Args:
        food_query: Free-text food description, e.g. "greek yogurt plain".
    """
    # Interim acknowledgement so voice users aren't left in silence while the
    # USDA lookup runs — streamed immediately via the ambient turn context.
    # Skipped if the user has already barged in / interrupted this turn.
    if context is not None and not context.is_cancelled:
        await context.send("Let me look that up.")

    try:
        result = await search_food(food_query)
    except USDALookupError as exc:
        return ToolResult(llm_response={"ok": False, "error": str(exc)})

    if not result["matches"]:
        return ToolResult(
            llm_response={"ok": False, "error": "no_match", "query": food_query}
        )

    return ToolResult(llm_response={"ok": True, **result})
