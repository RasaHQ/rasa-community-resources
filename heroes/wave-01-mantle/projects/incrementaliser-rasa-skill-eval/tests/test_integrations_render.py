"""Agent copies get an orchestrator model group from YAML LLM settings."""

from __future__ import annotations

from pathlib import Path

from rasa_skill_eval.agent_eval import (
    render_model_group,
    sweep_openai_api_key,
    write_endpoints,
    write_integrations,
    write_references_embeddings,
)
from rasa_skill_eval.config import LlmEndpointSettings


def test_local_model_group_uses_explicit_base_url() -> None:
    """Per-agent llama.cpp ports must not fall back to LLAMA_BASE_URL."""
    group = render_model_group(
        LlmEndpointSettings(
            provider="local",
            model="LFM2-1.2B",
            base_url="http://127.0.0.1:8082/v1",
        )
    )
    model = group["models"][0]
    assert model["provider"] == "self-hosted"
    assert model["api_base"] == "http://127.0.0.1:8082/v1"
    assert model["api_key"] == "${LOCAL_LLM_API_KEY}"


def test_local_30b_model_group_uses_explicit_base_url() -> None:
    """30B GGUF actors use the same self-hosted group shape as LFM/8B."""
    group = render_model_group(
        LlmEndpointSettings(
            id="muse-30b",
            provider="local",
            model="muse-glimmer-30b",
            base_url="http://127.0.0.1:8085/v1",
        )
    )
    model = group["models"][0]
    assert model["provider"] == "self-hosted"
    assert model["api_base"] == "http://127.0.0.1:8085/v1"
    assert model["model"] == "muse-glimmer-30b"
    assert model["api_key"] == "${LOCAL_LLM_API_KEY}"


def test_nvidia_model_group_is_self_hosted() -> None:
    """NIM uses the OpenAI-compatible NVIDIA integrate URL."""
    group = render_model_group(
        LlmEndpointSettings(provider="nvidia", model="meta/llama-3.1-70b-instruct")
    )
    model = group["models"][0]
    assert model["provider"] == "self-hosted"
    assert "integrate.api.nvidia.com" in model["api_base"]
    assert model["api_key"] == "${NVIDIA_API_KEY}"


def test_write_endpoints_drops_openai_key(tmp_path: Path) -> None:
    """Rasano endpoints.yml must not keep ${OPENAI_API_KEY} after rewrite."""
    (tmp_path / "endpoints.yml").write_text(
        "nlg:\n  type: rephrase\n  llm:\n    model_group: openai-llm\n"
        "model_groups:\n  - id: openai-llm\n    models:\n"
        "      - provider: openai\n        api_key: ${OPENAI_API_KEY}\n",
        encoding="utf-8",
    )
    write_endpoints(
        tmp_path,
        LlmEndpointSettings(provider="nvidia", model="meta/llama-3.1-70b-instruct"),
    )
    text = (tmp_path / "endpoints.yml").read_text(encoding="utf-8")
    assert "${OPENAI_API_KEY}" not in text
    assert "${NVIDIA_API_KEY}" in text
    assert "orchestrator" in text


def test_integrations_include_nvidia_embeddings(tmp_path: Path) -> None:
    """FAQ reference indexing must not fall back to the OpenAI embedder."""
    (tmp_path / "integrations.yml").write_text("llm: {}\n", encoding="utf-8")
    (tmp_path / "agent.yml").write_text("agent:\n  id: rasano\n", encoding="utf-8")
    chat = LlmEndpointSettings(provider="nvidia", model="meta/llama-3.1-70b-instruct")
    embed = LlmEndpointSettings(provider="nvidia", model="nvidia/nemotron-3-embed-1b")
    write_integrations(tmp_path, chat, embed)
    write_references_embeddings(tmp_path)
    integrations = (tmp_path / "integrations.yml").read_text(encoding="utf-8")
    assert "id: embeddings" in integrations
    assert "nemotron-3-embed-1b" in integrations
    assert "provider: openai" in integrations
    agent = (tmp_path / "agent.yml").read_text(encoding="utf-8")
    assert "embeddings: embeddings" in agent


def test_sweep_openai_api_key_rewrites_stray_files(tmp_path: Path) -> None:
    """Leftover ${OPENAI_API_KEY} in any text config becomes NVIDIA."""
    (tmp_path / "notes.yml").write_text("key: ${OPENAI_API_KEY}\n", encoding="utf-8")
    (tmp_path / "ok.yml").write_text("key: ${NVIDIA_API_KEY}\n", encoding="utf-8")
    assert sweep_openai_api_key(tmp_path) == 1
    assert "${OPENAI_API_KEY}" not in (tmp_path / "notes.yml").read_text(encoding="utf-8")
    assert "${NVIDIA_API_KEY}" in (tmp_path / "notes.yml").read_text(encoding="utf-8")
