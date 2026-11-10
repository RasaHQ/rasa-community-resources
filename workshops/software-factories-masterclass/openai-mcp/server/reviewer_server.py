#!/usr/bin/env python3
"""An MCP server whose one tool asks a reviewer about a card dispute.

    python reviewer_server.py              # stub reviewer, no network, serves 127.0.0.1:8941/mcp
    REVIEWER_BACKEND=openai-agents python reviewer_server.py   # NOT RUN in this repo: needs a key

Mantle reaches MCP servers over streamable HTTP only. The reviewer's answer is advice. It carries no
authority: the write that follows is gated by Mantle's own confirmation, not by this server.

The stub is deterministic and says so in every result (`backend: "stub"`). It exists so the
engine-side checks can run with no key and no network; it is not a model and proves nothing about one.
"""
from __future__ import annotations

import os
from typing import Literal

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel

VerdictName = Literal["looks_unauthorised", "looks_authorised", "unclear"]

HOST, PORT = "127.0.0.1", 8941

mcp = FastMCP("reviewer", host=HOST, port=PORT, stateless_http=True)


# An explicit return model publishes an outputSchema, so structuredContent is populated and Mantle
# hands the model a flat object, not a JSON string in a list of text parts (found in
# tutorials/rasa-hubspot-crm-tutorial/scripts/mcp_crm_server.py).
class Review(BaseModel):
    model_config = {"extra": "allow"}

    ok: bool
    verdict: VerdictName
    reason: str
    backend: str


class Verdict(BaseModel):
    """What the OpenAI agent must return. Strict (no extra keys) because the Agents SDK requires it;
    the tool's own result model above allows extras, and the SDK refuses that one as an output type."""

    verdict: VerdictName
    reason: str


def _stub(description: str) -> Review:
    text = description.lower()
    if any(word in text for word in ("stolen", "lost", "not me", "did not make", "didn't make")):
        return Review(ok=True, verdict="looks_unauthorised", reason="the caller says they did not make it", backend="stub")
    return Review(ok=True, verdict="unclear", reason="nothing in the description settles it", backend="stub")


def _openai_agent(description: str) -> Review:  # pragma: no cover - needs a key; not run here
    from agents import Agent, Runner, set_tracing_disabled

    set_tracing_disabled(True)
    agent = Agent(
        name="dispute-reviewer",
        instructions=(
            "You advise a bank assistant on one card dispute. Answer with a verdict of "
            "looks_unauthorised, looks_authorised or unclear, and one short reason. You approve nothing."
        ),
        output_type=Verdict,
    )
    result = Runner.run_sync(agent, description)
    review = result.final_output
    return Review(ok=True, verdict=review.verdict, reason=review.reason, backend="openai-agents")


@mcp.tool(description="Ask the reviewer about a card dispute. Returns advice only: a verdict and a reason.")
def ask_reviewer(description: str) -> Review:
    if os.environ.get("REVIEWER_BACKEND") == "openai-agents":
        return _openai_agent(description)
    return _stub(description)


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
