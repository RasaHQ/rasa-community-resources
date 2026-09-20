"""Anthropic Messages API client."""

from __future__ import annotations

from typing import Any

import httpx

from rasa_skill_eval.llm.types import ChatMessage, ChatResult

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"


class AnthropicClient:
    """Chat via Anthropic ``/v1/messages``."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        temperature: float = 0.0,
        max_tokens: int = 4096,
        timeout_sec: float = 300.0,
    ) -> None:
        """Store Anthropic settings."""
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout_sec = timeout_sec

    def complete(
        self,
        messages: list[ChatMessage],
        *,
        max_tokens: int | None = None,
        temperature: float | None = None,
        seed: int | None = None,
    ) -> ChatResult:
        """Return one assistant message. ``seed`` is ignored (API has no seed)."""
        del seed
        system_parts = [m.content for m in messages if m.role == "system"]
        chat = [
            {"role": m.role, "content": m.content}
            for m in messages
            if m.role in {"user", "assistant"}
        ]
        payload: dict[str, Any] = {
            "model": self.model,
            "max_tokens": max_tokens if max_tokens is not None else self.max_tokens,
            "temperature": temperature if temperature is not None else self.temperature,
            "messages": chat or [{"role": "user", "content": ""}],
        }
        if system_parts:
            payload["system"] = "\n\n".join(system_parts)
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        timeout = httpx.Timeout(
            connect=30.0,
            read=self.timeout_sec,
            write=30.0,
            pool=30.0,
        )
        with httpx.Client(timeout=timeout) as client:
            response = client.post(ANTHROPIC_URL, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
        text = _anthropic_text(data)
        usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
        prompt = usage.get("input_tokens")
        completion = usage.get("output_tokens")
        return ChatResult(
            text=text,
            prompt_tokens=int(prompt) if isinstance(prompt, (int, float)) else None,
            completion_tokens=int(completion) if isinstance(completion, (int, float)) else None,
            raw=data if isinstance(data, dict) else None,
        )


def _anthropic_text(data: Any) -> str:
    """Join text blocks from an Anthropic messages response."""
    if not isinstance(data, dict):
        return ""
    blocks = data.get("content")
    if not isinstance(blocks, list):
        return ""
    parts: list[str] = []
    for block in blocks:
        if isinstance(block, dict) and block.get("type") == "text":
            parts.append(str(block.get("text") or ""))
    return "".join(parts)
