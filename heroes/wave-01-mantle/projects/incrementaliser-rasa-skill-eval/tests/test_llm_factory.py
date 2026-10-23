"""LLM factory rejects unknown providers and missing keys."""

from __future__ import annotations

import pytest

from rasa_skill_eval.config import LlmEndpointSettings
from rasa_skill_eval.llm.factory import client_from_settings, try_client
from rasa_skill_eval.llm.openai_compat import OpenAICompatClient, _message_text


def test_unknown_provider_raises() -> None:
    """A typo in config.yaml must not silently fall through."""
    try:
        client_from_settings(LlmEndpointSettings(provider="nope", model="x"))
    except ValueError as exc:
        assert "Unknown LLM provider" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_try_client_returns_none_without_nvidia_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Missing NVIDIA_API_KEY is a skip, not a crash."""
    monkeypatch.setattr("rasa_skill_eval.llm.factory.load_dotenv", lambda: None)
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    client = try_client(LlmEndpointSettings(provider="nvidia", model="x"))
    assert client is None


def test_message_text_reads_openai_shape() -> None:
    """NVIDIA and llama.cpp share the OpenAI choices[0].message.content shape."""
    payload = {"choices": [{"message": {"content": "hello"}}], "usage": {"prompt_tokens": 1}}
    assert _message_text(payload) == "hello"


def test_local_client_uses_llama_base(monkeypatch: pytest.MonkeyPatch) -> None:
    """provider local reads LLAMA_BASE_URL."""
    monkeypatch.setenv("LLAMA_BASE_URL", "http://127.0.0.1:8081/v1")
    monkeypatch.setenv("LOCAL_LLM_API_KEY", "not-needed")
    client = client_from_settings(LlmEndpointSettings(provider="local", model="local-model"))
    assert isinstance(client, OpenAICompatClient)
    assert client.base_url.endswith("/v1")
    assert client.retry_on_timeout is False
    assert client.max_retries == 1


def test_factory_passes_timeout_sec(monkeypatch: pytest.MonkeyPatch) -> None:
    """YAML timeout_sec must reach the HTTP client."""
    monkeypatch.setenv("NVIDIA_API_KEY", "test-key")
    client = client_from_settings(
        LlmEndpointSettings(provider="nvidia", model="x", timeout_sec=600.0)
    )
    assert isinstance(client, OpenAICompatClient)
    assert client.timeout_sec == 600.0


def test_try_backup_improver_client(monkeypatch: pytest.MonkeyPatch) -> None:
    """Backup improver client is created when backup_model is present and key is set."""
    from rasa_skill_eval.config import ImproverSettings
    from rasa_skill_eval.llm.factory import try_backup_improver_client

    monkeypatch.setenv("NVIDIA_API_KEY", "test-key")
    settings = ImproverSettings(
        provider="nvidia",
        model="moonshotai/kimi-k3",
        backup_model="meta/llama-3.1-70b-instruct",
    )
    backup = try_backup_improver_client(settings)
    assert backup is not None
    assert isinstance(backup, OpenAICompatClient)
    assert backup.model == "meta/llama-3.1-70b-instruct"


def test_try_backup_client_uses_judge_backup(monkeypatch: pytest.MonkeyPatch) -> None:
    """Judge backup_model builds a second ChatClient on the same provider."""
    from rasa_skill_eval.llm.factory import try_backup_client

    monkeypatch.setenv("NVIDIA_API_KEY", "test-key")
    settings = LlmEndpointSettings(
        provider="nvidia",
        model="nvidia/nemotron-3-super-120b-a12b",
        backup_model="meta/llama-3.1-70b-instruct",
    )
    backup = try_backup_client(settings)
    assert backup is not None
    assert isinstance(backup, OpenAICompatClient)
    assert backup.model == "meta/llama-3.1-70b-instruct"


def test_backup_endpoint_switches_provider_to_openai(monkeypatch: pytest.MonkeyPatch) -> None:
    """backup_provider: openai uses OPENAI_API_KEY and api.openai.com."""
    from rasa_skill_eval.llm.factory import OPENAI_BASE, backup_endpoint, try_backup_client

    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    settings = LlmEndpointSettings(
        provider="nvidia",
        model="nvidia/nemotron-3-super-120b-a12b",
        backup_provider="openai",
        backup_model="gpt-4.1-mini",
    )
    backup = backup_endpoint(settings)
    assert backup is not None
    assert backup.provider == "openai"
    assert backup.model == "gpt-4.1-mini"
    assert backup.base_url is None
    client = try_backup_client(settings)
    assert client is not None
    assert isinstance(client, OpenAICompatClient)
    assert client.model == "gpt-4.1-mini"
    assert client.base_url.rstrip("/") == OPENAI_BASE.rstrip("/")

