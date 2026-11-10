"""Scripted native CrewAI execution; does not make provider requests."""

from __future__ import annotations
import json
from crewai import Crew
from crewai.llms.base_llm import BaseLLM
from pydantic import Field, PrivateAttr
from .acceptance import Checklist, PUBLIC_SOURCES
from .runtime import create_claim_crew


class ScriptedModel(BaseLLM):
    responses: list[str] = Field(default_factory=list)
    _index: int = PrivateAttr(default=0)

    def call(
        self,
        messages,
        tools=None,
        callbacks=None,
        available_functions=None,
        from_task=None,
        from_agent=None,
        response_model=None,
    ):
        if self._index >= len(self.responses):
            raise AssertionError("Unexpected additional fixture model call")
        text = self.responses[self._index]
        self._index += 1
        return text


def create_fixture(claim_type: str, unavailable: bool = False) -> Crew:
    source = PUBLIC_SOURCES[claim_type]
    checklist = Checklist(claim_type=claim_type, documents=source.required_documents)
    model = ScriptedModel(
        model="native-fixture",
        responses=[
            "Thought: Read the public claim source.\nAction: read_claim_source\nAction Input: {}",
            "Thought: Finish the scripted source task.\nFinal Answer: "
            + source.model_dump_json(),
            "Thought: Finish the scripted checklist task.\nFinal Answer: "
            + checklist.model_dump_json(),
        ],
    )
    return create_claim_crew(claim_type, model, unavailable=unavailable)
