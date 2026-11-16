"""Native tools for the shop assistant."""
from rasa.mantle.tools.decorator import tool
from rasa.mantle.tools.result import ToolResult
from typing import Literal
from shop_demo.assistant import catalog_tool, basket_tool, order_tool, clarify_tool


@tool(description="Read product codes, names, exact prices and available quantities before discussing a basket.")
async def product_catalog() -> ToolResult:
    return ToolResult(llm_response=await catalog_tool())


@tool(description="Price a basket without placing it. Each item has code and quantity. The host sends its exact review.")
async def price_basket(items: list[dict]) -> ToolResult:
    return ToolResult(llm_response=await basket_tool(items))


@tool(description="Read the latest order placed in this operator conversation.")
async def order_progress() -> ToolResult:
    return ToolResult(llm_response=await order_tool())


@tool(description="Ask for a missing product, quantity, or both before pricing a basket.")
async def ask_basket_details(missing: Literal["product", "quantity", "both"]) -> ToolResult:
    return ToolResult(llm_response=await clarify_tool(missing))
