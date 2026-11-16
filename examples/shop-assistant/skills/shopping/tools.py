"""Native tools for the shop assistant."""
from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult
from typing import Literal
from shop_demo.assistant import catalog_tool, basket_tool, order_tool, clarify_tool

# Rasa supplies ToolContext when it executes a native tool. It is kept out of
# the model's JSON arguments; every function must still accept the parameter.

@tool(description="Read product codes, names, exact prices and available quantities before discussing a basket.")
async def product_catalog(*, context: ToolContext) -> ToolResult:
    """Read the catalog so names, prices, and stock come from the shop data."""
    return ToolResult(llm_response=await catalog_tool())


@tool(description="Price a basket without placing it. Each item has code and quantity. The host sends its exact review.")
async def price_basket(items: list[dict], *, context: ToolContext) -> ToolResult:
    """Calculate a review; the host must receive a later confirm before ordering."""
    return ToolResult(llm_response=await basket_tool(items))


@tool(description="Read the latest order placed in this operator conversation.")
async def order_progress(*, context: ToolContext) -> ToolResult:
    """Read the last recorded order so the model does not invent its status."""
    return ToolResult(llm_response=await order_tool())


@tool(description="Ask for a missing product, quantity, or both before pricing a basket.")
async def ask_basket_details(missing: Literal["product", "quantity", "both"], *, context: ToolContext) -> ToolResult:
    """Ask for missing details instead of guessing a product or quantity."""
    return ToolResult(llm_response=await clarify_tool(missing))
