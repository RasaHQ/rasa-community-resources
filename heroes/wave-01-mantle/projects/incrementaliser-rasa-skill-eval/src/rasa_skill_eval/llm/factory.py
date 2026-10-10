"""Build a chat client from YAML endpoint settings and ``.env`` secrets."""

from __future__ import annotations

import os

from dotenv import load_dotenv
from loguru import logger

from rasa_skill_eval.config import LlmEndpointSettings
from rasa_skill_eval.llm.anthropic import AnthropicClient
from rasa_skill_eval.llm.openai_compat import OpenAICompatClient, RateLimitCircuit
from rasa_skill_eval.llm.types import ChatClient

NVIDIA_BASE = "https://integrate.api.nvidia.com/v1"
OPENAI_BASE = "https://api.openai.com/v1"
DEFAULT_LOCAL_BASE = "http://127.0.0.1:8081/v1"


def client_from_settings(
    settings: LlmEndpointSettings,
    *,
    max_retries: int | None = None,
    max_retry_after_sec: float | None = None,
    overall_timeout_sec: float | None = None,
    circuit: RateLimitCircuit | None = None,
) -> ChatClient:
    """Return a live client. Raises ``ValueError`` if the key or provider is missing."""
    load_dotenv()
    provider = settings.provider.strip().lower()
    retry_kwargs: dict[str, object] = {}
    if max_retries is not None:
        retry_kwargs["max_retries"] = max_retries
    if max_retry_after_sec is not None:
        retry_kwargs["max_retry_after_sec"] = max_retry_after_sec
    if overall_timeout_sec is not None:
        retry_kwargs["overall_timeout_sec"] = overall_timeout_sec
    if circuit is not None:
        retry_kwargs["circuit"] = circuit
    if provider == "nvidia":
        key = os.getenv("NVIDIA_API_KEY", "").strip()
        if not key:
            raise ValueError("NVIDIA_API_KEY is not set")
        return OpenAICompatClient(
            base_url=settings.base_url or NVIDIA_BASE,
            api_key=key,
            model=settings.model,
            temperature=settings.temperature,
            max_tokens=settings.max_tokens,
            timeout_sec=settings.timeout_sec,
            retry_on_timeout=True,
            **retry_kwargs,
        )
    if provider == "openai":
        key = os.getenv("OPENAI_API_KEY", "").strip()
        if not key:
            raise ValueError("OPENAI_API_KEY is not set")
        return OpenAICompatClient(
            base_url=settings.base_url or OPENAI_BASE,
            api_key=key,
            model=settings.model,
            temperature=settings.temperature,
            max_tokens=settings.max_tokens,
            timeout_sec=settings.timeout_sec,
            **retry_kwargs,
        )
    if provider in {"local", "llama", "llamacpp", "llama.cpp"}:
        base = settings.base_url or os.getenv("LLAMA_BASE_URL", DEFAULT_LOCAL_BASE)
        key = os.getenv("LOCAL_LLM_API_KEY", "not-needed")
        local_retries = 1 if max_retries is None else max_retries
        return OpenAICompatClient(
            base_url=base,
            api_key=key,
            model=settings.model,
            temperature=settings.temperature,
            max_tokens=settings.max_tokens,
            timeout_sec=settings.timeout_sec,
            retry_on_timeout=False,
            max_retries=local_retries,
            **{
                key: value
                for key, value in retry_kwargs.items()
                if key != "max_retries"
            },
        )
    if provider == "anthropic":
        key = os.getenv("ANTHROPIC_API_KEY", "").strip()
        if not key:
            raise ValueError("ANTHROPIC_API_KEY is not set")
        return AnthropicClient(
            api_key=key,
            model=settings.model,
            temperature=settings.temperature,
            max_tokens=settings.max_tokens,
            timeout_sec=settings.timeout_sec,
        )
    raise ValueError(f"Unknown LLM provider: {settings.provider}")


def try_client(
    settings: LlmEndpointSettings,
    **kwargs: object,
) -> ChatClient | None:
    """Return a client or None when the key/provider is unavailable."""
    try:
        return client_from_settings(settings, **kwargs)  # type: ignore[arg-type]
    except ValueError as exc:
        logger.info("LLM client skipped: {}", exc)
        return None


def backup_endpoint(settings: LlmEndpointSettings) -> LlmEndpointSettings | None:
    """Return a copy of ``settings`` pointed at the backup model and provider."""
    backup_model = getattr(settings, "backup_model", None)
    if not backup_model:
        return None
    updates: dict[str, object] = {"model": str(backup_model), "id": None}
    backup_provider = getattr(settings, "backup_provider", None)
    if backup_provider:
        provider = str(backup_provider).strip().lower()
        updates["provider"] = provider
        if provider != settings.provider.strip().lower():
            updates["base_url"] = None
    return settings.model_copy(update=updates)


def try_backup_client(
    settings: LlmEndpointSettings,
    **kwargs: object,
) -> ChatClient | None:
    """Return a backup client when ``backup_model`` is configured."""
    backup = backup_endpoint(settings)
    if backup is None:
        return None
    return try_client(backup, **kwargs)


def try_backup_improver_client(settings: LlmEndpointSettings) -> ChatClient | None:
    """Return a backup client for the improver model if configured."""
    return try_backup_client(settings)
