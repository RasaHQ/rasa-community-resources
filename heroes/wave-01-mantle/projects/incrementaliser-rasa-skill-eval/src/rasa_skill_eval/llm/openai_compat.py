"""OpenAI-compatible chat completions: NVIDIA NIM, OpenAI, llama.cpp."""

from __future__ import annotations

import time
from typing import Any

import httpx
from loguru import logger

from rasa_skill_eval.llm.types import ChatMessage, ChatResult
from rasa_skill_eval.proc import Deadline

_RETRY_STATUSES = frozenset({429, 502, 503, 504})
_GONE_STATUSES = frozenset({410})


class RateLimitTripped(RuntimeError):
    """The run-level 429 circuit breaker is open."""


class RateLimitCircuit:
    """Trip after consecutive exhausted 429/503 sequences."""

    def __init__(self, trip_after: int = 3) -> None:
        """Store how many exhausted rate-limit sequences open the breaker."""
        self.trip_after = max(1, trip_after)
        self.failures = 0
        self.tripped = False
        self.reason = ""

    def reset(self) -> None:
        """Clear failure counts (tests and a fresh eval-all)."""
        self.failures = 0
        self.tripped = False
        self.reason = ""

    def check(self) -> None:
        """Raise when a previous sequence already tripped the breaker."""
        if self.tripped:
            raise RateLimitTripped(self.reason or "LLM rate-limit circuit open")

    def record_success(self) -> None:
        """A completed call clears the consecutive 429 streak."""
        self.failures = 0

    def record_exhausted_rate_limit(self, message: str) -> None:
        """Count one fully retried 429/503 sequence and maybe trip."""
        self.failures += 1
        if self.failures >= self.trip_after:
            self.tripped = True
            self.reason = message
            logger.warning("LLM rate-limit circuit open after {} sequences", self.failures)


DEFAULT_CIRCUIT = RateLimitCircuit()


class OpenAICompatClient:
    """POST ``/chat/completions`` against an OpenAI-shaped base URL."""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        temperature: float = 0.0,
        max_tokens: int = 4096,
        timeout_sec: float = 300.0,
        extra_headers: dict[str, str] | None = None,
        max_retries: int = 5,
        max_retry_after_sec: float = 30.0,
        retry_on_timeout: bool = True,
        overall_timeout_sec: float | None = None,
        circuit: RateLimitCircuit | None = None,
    ) -> None:
        """Store endpoint settings. No network happens until ``complete``."""
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout_sec = timeout_sec
        self.extra_headers = extra_headers or {}
        self.max_retries = max(0, max_retries)
        self.max_retry_after_sec = max(0.0, max_retry_after_sec)
        self.retry_on_timeout = retry_on_timeout
        if overall_timeout_sec is None:
            self.overall_timeout_sec = timeout_sec
        elif overall_timeout_sec <= 0:
            self.overall_timeout_sec = 1e12
        else:
            self.overall_timeout_sec = overall_timeout_sec
        self.circuit = circuit if circuit is not None else DEFAULT_CIRCUIT

    def complete(
        self,
        messages: list[ChatMessage],
        *,
        max_tokens: int | None = None,
        temperature: float | None = None,
        seed: int | None = None,
    ) -> ChatResult:
        """Call chat completions and return text plus usage."""
        self.circuit.check()
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "max_tokens": max_tokens if max_tokens is not None else self.max_tokens,
            "temperature": temperature if temperature is not None else self.temperature,
            "stream": False,
        }
        if seed is not None:
            payload["seed"] = seed
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
            **self.extra_headers,
        }
        url = f"{self.base_url}/chat/completions"
        deadline = Deadline(self.overall_timeout_sec)
        data: Any = None
        last_error: Exception | None = None
        attempts = self.max_retries + 1
        saw_rate_limit = False
        with httpx.Client() as client:
            for attempt in range(attempts):
                remaining = deadline.remaining()
                if remaining <= 0:
                    break
                timeout = httpx.Timeout(
                    connect=min(30.0, remaining),
                    read=min(self.timeout_sec, remaining),
                    write=min(30.0, remaining),
                    pool=min(30.0, remaining),
                )
                try:
                    response = client.post(
                        url, headers=headers, json=payload, timeout=timeout
                    )
                    if response.status_code in _GONE_STATUSES:
                        response.raise_for_status()
                    if response.status_code in _RETRY_STATUSES and attempt < attempts - 1:
                        saw_rate_limit = True
                        wait = retry_wait_sec(
                            response, attempt, cap_sec=self.max_retry_after_sec
                        )
                        if wait >= deadline.remaining():
                            last_error = httpx.HTTPStatusError(
                                f"HTTP {response.status_code}",
                                request=response.request,
                                response=response,
                            )
                            break
                        logger.warning(
                            "LLM HTTP {} from {} model={}; retry in {:.1f}s (attempt {}/{})",
                            response.status_code,
                            url,
                            self.model,
                            wait,
                            attempt + 1,
                            attempts,
                        )
                        time.sleep(wait)
                        continue
                    response.raise_for_status()
                    data = response.json()
                    break
                except httpx.HTTPError as exc:
                    last_error = exc
                    retryable = _retryable_error(exc, retry_on_timeout=self.retry_on_timeout)
                    if isinstance(exc, httpx.HTTPStatusError) and exc.response is not None:
                        if exc.response.status_code in _RETRY_STATUSES:
                            saw_rate_limit = True
                    if not retryable or attempt >= attempts - 1:
                        if saw_rate_limit:
                            self.circuit.record_exhausted_rate_limit(str(exc))
                        raise
                    wait = min(float(2**attempt), self.max_retry_after_sec, deadline.remaining())
                    if wait <= 0:
                        if saw_rate_limit:
                            self.circuit.record_exhausted_rate_limit(str(exc))
                        raise
                    logger.warning(
                        "LLM request failed ({}); retry in {:.1f}s (attempt {}/{})",
                        exc,
                        wait,
                        attempt + 1,
                        attempts,
                    )
                    time.sleep(wait)
            else:
                if last_error is not None:
                    if saw_rate_limit:
                        self.circuit.record_exhausted_rate_limit(str(last_error))
                    raise last_error
                raise RuntimeError(f"LLM retries exhausted for {url}")
        if data is None:
            if last_error is not None:
                if saw_rate_limit:
                    self.circuit.record_exhausted_rate_limit(str(last_error))
                raise last_error
            raise TimeoutError(f"LLM overall deadline exhausted for {url}")
        self.circuit.record_success()
        text = _message_text(data)
        usage: dict[str, Any] = {}
        if isinstance(data, dict) and isinstance(data.get("usage"), dict):
            usage = data["usage"]
        prompt = usage.get("prompt_tokens")
        completion = usage.get("completion_tokens")
        return ChatResult(
            text=text,
            prompt_tokens=int(prompt) if isinstance(prompt, (int, float)) else None,
            completion_tokens=int(completion) if isinstance(completion, (int, float)) else None,
            raw=data if isinstance(data, dict) else None,
        )


def _retryable_error(exc: httpx.HTTPError, *, retry_on_timeout: bool) -> bool:
    """Return True when this error class should be retried."""
    if isinstance(exc, httpx.TimeoutException):
        return retry_on_timeout
    if isinstance(exc, httpx.NetworkError):
        return True
    if isinstance(exc, httpx.HTTPStatusError) and exc.response is not None:
        return exc.response.status_code in _RETRY_STATUSES
    return False


def retry_wait_sec(
    response: httpx.Response,
    attempt: int,
    *,
    cap_sec: float = 30.0,
) -> float:
    """Honor ``Retry-After`` when present, else exponential backoff, capped."""
    raw = response.headers.get("Retry-After")
    wait = float(2**attempt)
    if raw:
        try:
            wait = max(0.0, float(raw))
        except ValueError:
            pass
    return min(wait, cap_sec)


def _message_text(data: Any) -> str:
    """Extract assistant text from an OpenAI-shaped body."""
    if not isinstance(data, dict):
        return ""
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    first = choices[0]
    if not isinstance(first, dict):
        return ""
    message = first.get("message")
    if isinstance(message, dict):
        content = message.get("content")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    parts.append(str(item.get("text") or ""))
            return "".join(parts)
    text = first.get("text")
    return str(text) if text is not None else ""
