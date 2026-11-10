import asyncio
import os
from pathlib import Path

from agno.models.openai import OpenAIChat
from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult

from shop_adviser.service import AdviserService

SERVICE = None


def service():
    global SERVICE
    if SERVICE is None:
        root = Path(__file__).resolve().parents[2]
        SERVICE = AdviserService(
            root / ".state" / "public-shop.sqlite",
            lambda: OpenAIChat(
                id=os.environ.get("SHOP_MODEL", "gpt-5.5-2026-04-23"),
                timeout=10,
                max_retries=0,
            ),
        )
    return SERVICE


@tool(
    description="Ask the existing Agno adviser about the public synthetic Willow Shop hand cream. Supply the question only; application code resolves its demo profile and conversation. Does not place orders or update preferences."
)
async def ask_product_adviser(question: str, context: ToolContext = None) -> ToolResult:
    from rasa.mantle.orchestration.turn_context import current_turn_context

    sender = current_turn_context().sender_id
    return ToolResult(
        llm_response=await asyncio.to_thread(service().answer, sender, question)
    )
