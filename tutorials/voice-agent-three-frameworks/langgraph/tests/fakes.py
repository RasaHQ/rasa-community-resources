"""Offline stand-ins: a scripted chat model, a scripted classifier and a fake TTS. No network."""

from __future__ import annotations

import itertools
from typing import Any, Iterator, Optional

from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult

_ids = itertools.count(1)


def call(name: str, **args: Any) -> AIMessage:
    """An AI message with one tool call."""
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": f"call_{next(_ids)}"}])


def say(text: str) -> AIMessage:
    return AIMessage(content=text)


class ScriptedModel(BaseChatModel):
    """Returns the scripted messages in order and records the tools offered on each call."""

    script: list = []
    offered: list = []
    seen: list = []

    @property
    def _llm_type(self) -> str:
        return "scripted"

    def bind_tools(self, tools: Any, **kwargs: Any) -> "ScriptedModel":
        self.offered.append([getattr(t, "name", None) or t.get("name") for t in tools])
        return self

    def _next(self, messages: list[BaseMessage]) -> AIMessage:
        self.seen.append(list(messages))
        if not self.script:
            return AIMessage(content="Is there anything else?")
        message = self.script.pop(0)
        return message.model_copy(update={"id": f"run-{next(_ids)}"})

    def _generate(self, messages: list[BaseMessage], stop: Optional[list[str]] = None,
                  run_manager: Optional[CallbackManagerForLLMRun] = None, **kwargs: Any) -> ChatResult:
        return ChatResult(generations=[ChatGeneration(message=self._next(messages))])

    def _stream(self, messages: list[BaseMessage], stop: Optional[list[str]] = None,
                run_manager: Optional[CallbackManagerForLLMRun] = None, **kwargs: Any) -> Iterator[ChatGenerationChunk]:
        message = self._next(messages)
        words = message.content.split(" ") if message.content else []
        for i, word in enumerate(words):
            chunk = AIMessageChunk(content=word + (" " if i < len(words) - 1 else ""), id=message.id)
            if run_manager:
                run_manager.on_llm_new_token(chunk.content, chunk=ChatGenerationChunk(message=chunk))
            yield ChatGenerationChunk(message=chunk)
        if message.tool_calls:
            chunk = AIMessageChunk(content="", id=message.id, tool_call_chunks=[
                {"name": tc["name"], "args": __import__("json").dumps(tc["args"]), "id": tc["id"], "index": i}
                for i, tc in enumerate(message.tool_calls)])
            if run_manager:
                run_manager.on_llm_new_token("", chunk=ChatGenerationChunk(message=chunk))
            yield ChatGenerationChunk(message=chunk)


def yes_no_classifier(question: str, answer: str) -> Any:
    """Offline stand-in for the model's yes/no judgement: a leading yes is a yes."""

    async def run() -> bool:
        return answer.lower().lstrip().startswith(("yes", "yeah", "sure"))

    return run()


class FakeTTS:
    """0.25 s of a quiet tone per call, so markers and latency can be checked offline."""

    def __init__(self) -> None:
        self.texts: list[str] = []
        self.last_timings: dict = {}

    async def synthesize(self, text: str) -> bytes:
        self.texts.append(text)
        self.last_timings = {"chars": len(text), "headers_s": 0.01, "total_s": 0.02, "audio_s": 0.25}
        return (b"\x10\x00\xf0\xff" * 3000)

    async def close(self) -> None:
        return None
