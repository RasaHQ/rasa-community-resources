"""The existing native adviser keeps its tool, model and SQLite memory."""

from pathlib import Path
from typing import Literal

from agno.agent import Agent
from agno.db.schemas.memory import UserMemory
from agno.db.sqlite import SqliteDb
from agno.models.base import Model
from pydantic import BaseModel, ConfigDict, Field

from shop_adviser.scope_binding import resolve_demo_scope

PREFERENCE = "Synthetic Willow Shop customer A prefers fragrance-free products."


def lookup_product() -> str:
    """Return the public synthetic hand-cream record, with no customer information."""
    return '{"id":"WS-HAND-01","name":"Plain hand cream","fragrance":"none"}'


class ProductAdvice(BaseModel):
    model_config = ConfigDict(extra="forbid")
    product_id: Literal["WS-HAND-01"]
    explanation: str = Field(min_length=1, max_length=800)


def create_adviser(db_path: Path, model: Model) -> Agent:
    return Agent(
        name="Willow Shop public adviser",
        model=model,
        db=SqliteDb(db_file=str(db_path)),
        tools=[lookup_product],
        instructions="Explain the public synthetic product record. Use preferences only as context for this read-only advice. Do not place orders or change a profile.",
        output_schema=ProductAdvice,
        add_memories_to_context=True,
        add_history_to_context=True,
        update_memory_on_run=False,
        telemetry=False,
    )


def seed_public_preference(db_path: Path) -> None:
    db = SqliteDb(db_file=str(db_path))
    db.upsert_user_memory(
        UserMemory(
            memory=PREFERENCE,
            memory_id="willow-public-demo-a",
            user_id="customer-a",
        )
    )


def advise_for_demo_sender(agent: Agent, sender_id: str, question: str) -> dict:
    scope = resolve_demo_scope(sender_id)
    if scope is None:
        return {"status": "unknown_demo_sender"}
    if not isinstance(question, str) or not question.strip() or len(question) > 1000:
        return {"status": "invalid_question"}
    try:
        result = agent.run(question, user_id=scope.user_id, session_id=scope.session_id)
        advice = (
            result.content
            if isinstance(result.content, ProductAdvice)
            else ProductAdvice.model_validate_json(result.content)
        )
        return {"status": "ready", **advice.model_dump()}
    except Exception:
        return {"status": "advice_unavailable"}
