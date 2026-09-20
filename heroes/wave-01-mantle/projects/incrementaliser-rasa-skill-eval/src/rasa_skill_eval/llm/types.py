"""Shared chat types for every LLM provider."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ChatMessage:
    """One chat turn."""

    role: str
    content: str


@dataclass(frozen=True)
class ChatResult:
    """Model reply plus usage when the provider reports it."""

    text: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    raw: dict[str, object] | None = None

    @property
    def total_tokens(self) -> int | None:
        """Sum of prompt and completion tokens when both are known."""
        if self.prompt_tokens is None or self.completion_tokens is None:
            return None
        return self.prompt_tokens + self.completion_tokens


class ChatClient(Protocol):
    """Minimal chat-completions client."""

    def complete(
        self,
        messages: list[ChatMessage],
        *,
        max_tokens: int | None = None,
        temperature: float | None = None,
        seed: int | None = None,
    ) -> ChatResult:
        """Return one assistant completion."""
        ...
