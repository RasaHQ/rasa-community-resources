"""Config loads llm.agents list."""

from __future__ import annotations

from rasa_skill_eval.config import LlmEndpointSettings, load_config


def test_config_loads_agents_list() -> None:
    """config.yaml exposes a non-empty llm.agents factor."""
    cfg = load_config()
    assert len(cfg.llm.agents) >= 1
    assert all(isinstance(a, LlmEndpointSettings) for a in cfg.llm.agents)
    assert cfg.llm.agents[0].path_id()


def test_config_agent_size_ladder() -> None:
    """Default actors are two LFM, two local 8B, two local 30B GGUF."""
    cfg = load_config()
    ids = [a.path_id() for a in cfg.llm.agents]
    assert ids == [
        "lfm-1.2b",
        "lfm-2.6b",
        "llama-8b",
        "nemotron-8b",
        "muse-30b",
        "gemma4-31b",
    ]
    assert cfg.llm.agents[0].base_url == "http://127.0.0.1:8082/v1"
    assert cfg.llm.agents[1].base_url == "http://127.0.0.1:8081/v1"
    assert cfg.llm.agents[4].provider == "local"
    assert cfg.llm.agents[4].base_url == "http://127.0.0.1:8085/v1"
    assert cfg.llm.agents[4].model == "muse-glimmer-30b"
    assert cfg.llm.agents[5].provider == "local"
    assert cfg.llm.agents[5].base_url == "http://127.0.0.1:8086/v1"
    assert cfg.llm.agents[5].model == "gemma-4-31b-it"
    assert cfg.llm.judge.model == "nvidia/nemotron-3-super-120b-a12b"
    assert cfg.llm.improver.provider == "nvidia"
    assert cfg.llm.embeddings.provider == "nvidia"
    assert cfg.eval.llama_n_gpu_layers == 99
    assert cfg.eval.llama_flash_attn is True
    assert cfg.eval.llama_parallel == 1
    assert cfg.eval.llama_threads == 8


def test_eval_stage_timeouts_load_from_yaml() -> None:
    """Stage budgets used by Layer B must come from config.yaml."""
    cfg = load_config()
    assert cfg.eval.scenario_timeout_sec == 360
    assert cfg.eval.local_startup_timeout_sec == 300
    assert cfg.eval.sync_timeout_sec == 300
    assert cfg.eval.train_timeout_sec == 900
    assert cfg.eval.rasa_startup_timeout_sec == 180
    assert cfg.eval.consecutive_timeout_limit == 3
    assert cfg.eval.max_retry_after_sec == 300
    assert cfg.eval.llm_rate_limit_trip_after == 3
    assert cfg.eval.judge_max_retries == 12


def test_path_id_sanitizes_slashes() -> None:
    """Model ids with slashes become path-safe."""
    settings = LlmEndpointSettings(id="meta/llama", model="meta/llama-3.1-8b-instruct")
    assert "/" not in settings.path_id()


def test_improver_config_loads_backup_model() -> None:
    """Improver settings load backup model from yaml."""
    cfg = load_config()
    assert cfg.llm.improver.model == "moonshotai/kimi-k3"
    assert cfg.llm.improver.backup_model == "meta/llama-3.1-70b-instruct"


def test_judge_and_nvidia_models_load_from_yaml() -> None:
    """Judge backup and live SkillEvaluator models are pinned in config.yaml."""
    cfg = load_config()
    assert cfg.llm.judge.backup_model == "gpt-4.1-mini"
    assert cfg.llm.judge.backup_provider == "openai"
    assert cfg.nvidia.rubric_model == "nvidia/nemotron-3-super-120b-a12b"
    assert cfg.nvidia.embedding_model == "nvidia/nemotron-3-embed-1b"
