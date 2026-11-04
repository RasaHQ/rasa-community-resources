"""Typed settings loaded from ``config.yaml``. Secrets stay in ``.env``."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

from rasa_skill_eval import PROJECT_ROOT


class ProjectSettings(BaseModel):
    """Engine pin written into reports and run metadata."""

    rasa_pro_version: str
    engine: str


class PathSettings(BaseModel):
    """Project-relative directories that callers actually resolve."""

    runs_dir: str = "runs"
    data_dir: str = "data"
    writing_for_agents_dir: str = ".cursor/skills/writing-for-agents"
    unslop_dir: str = "data/skills/unslop"


class NvidiaSettings(BaseModel):
    """SkillEvaluator CLI defaults. Native Mantle folders are never the target."""

    checks: str = "schema,pii,license,quality,unicode,lint"
    min_score: int = 70
    quality_timeout_sec: int = 180
    validate_timeout_sec: int = 300
    rubric_model: str = "nvidia/nemotron-3-super-120b-a12b"
    embedding_model: str = "nvidia/nemotron-3-embed-1b"


class ProjectionSettings(BaseModel):
    """License, author, and compatibility fields written onto projected copies."""

    license: str = "Apache-2.0"
    author: str = "RasaHQ <hi@rasa.com>"
    compatibility: str = "Rasa Mantle (rasa-pro 3.20.0.dev6)"
    metadata_version: str = "0.1.0"


class LlmEndpointSettings(BaseModel):
    """One chat endpoint plus optional backup_provider/backup_model. Secrets stay in ``.env``."""

    provider: str = "nvidia"
    model: str = "meta/llama-3.1-70b-instruct"
    temperature: float = 0.0
    max_tokens: int = 4096
    timeout_sec: float = 300.0
    base_url: str | None = None
    id: str | None = None
    backup_model: str | None = None
    backup_provider: str | None = None

    def path_id(self) -> str:
        """Sanitize ``id`` (or ``model``) for run-folder path segments."""
        raw = (self.id or self.model or "default").strip() or "default"
        return raw.replace("/", "_").replace("\\", "_").replace(" ", "_")


class ImproverSettings(LlmEndpointSettings):
    """Primary improver endpoint plus optional backup model for resilience/retry."""

    provider: str = "nvidia"
    model: str = "moonshotai/kimi-k3"
    temperature: float = 0.2
    max_tokens: int = 8192
    timeout_sec: float = 600.0
    backup_model: str = "meta/llama-3.1-70b-instruct"


class LlmSettings(BaseModel):
    """Improver, agent-core list, judge, and FAQ embeddings endpoints."""

    improver: ImproverSettings = Field(
        default_factory=lambda: ImproverSettings()
    )
    agents: list[LlmEndpointSettings] = Field(
        default_factory=lambda: [
            LlmEndpointSettings(
                id="lfm-1.2b",
                provider="local",
                model="LFM2-1.2B",
                base_url="http://127.0.0.1:8082/v1",
            ),
            LlmEndpointSettings(
                id="lfm-2.6b",
                provider="local",
                model="LFM2-2.6B",
                base_url="http://127.0.0.1:8081/v1",
            ),
            LlmEndpointSettings(
                id="llama-8b",
                provider="local",
                model="llama-3.1-8b-instruct",
                base_url="http://127.0.0.1:8083/v1",
            ),
            LlmEndpointSettings(
                id="nemotron-8b",
                provider="local",
                model="llama-3.1-nemotron-nano-8b-v1",
                base_url="http://127.0.0.1:8084/v1",
            ),
            LlmEndpointSettings(
                id="muse-30b",
                provider="local",
                model="muse-glimmer-30b",
                base_url="http://127.0.0.1:8085/v1",
            ),
            LlmEndpointSettings(
                id="gemma4-31b",
                provider="local",
                model="gemma-4-31b-it",
                base_url="http://127.0.0.1:8086/v1",
            ),
        ]
    )
    judge: LlmEndpointSettings = Field(
        default_factory=lambda: LlmEndpointSettings(
            provider="nvidia",
            model="nvidia/nemotron-3-super-120b-a12b",
            temperature=0.0,
            backup_provider="openai",
            backup_model="gpt-4.1-mini",
        )
    )
    embeddings: LlmEndpointSettings = Field(
        default_factory=lambda: LlmEndpointSettings(
            provider="nvidia",
            model="nvidia/nemotron-3-embed-1b",
            temperature=0.0,
        )
    )


class TsrWeights(BaseModel):
    """Per-component weights for the headline weighted TSR."""

    skill_started: float = 0.20
    tool_correct: float = 0.30
    memory_set: float = 0.20
    confirmation: float = 0.15
    safety: float = 0.15

    def as_dict(self) -> dict[str, float]:
        """Return component name to weight."""
        return {
            "skill_started": self.skill_started,
            "tool_correct": self.tool_correct,
            "memory_set": self.memory_set,
            "confirmation": self.confirmation,
            "safety": self.safety,
        }


class EvalSettings(BaseModel):
    """Live Mantle scenario evaluation knobs and stage deadlines."""

    repeats: int = 3
    turn_timeout_sec: float = 180.0
    scenario_timeout_sec: float = 360.0
    local_startup_timeout_sec: float = 300.0
    sync_timeout_sec: float = 300.0
    train_timeout_sec: float = 900.0
    rasa_startup_timeout_sec: float = 180.0
    consecutive_timeout_limit: int = 3
    max_retry_after_sec: float = 300.0
    llm_rate_limit_trip_after: int = 3
    judge_max_retries: int = 12
    llama_n_gpu_layers: int = 99
    llama_flash_attn: bool = True
    llama_parallel: int = 1
    llama_threads: int = 8
    tsr_weights: TsrWeights = Field(default_factory=TsrWeights)


class CorpusEntry(BaseModel):
    """One git sparse-checkout source."""

    repo: str
    sparse_path: str = ""
    dest: str


class MlflowSettings(BaseModel):
    """Optional remote MLflow endpoint for progress telemetry."""

    tracking_uri: str | None = None


class TrackingSettings(BaseModel):
    """Optional external progress tracking configuration."""

    mlflow: MlflowSettings = Field(default_factory=MlflowSettings)


class AppConfig(BaseModel):
    """Root config.yaml schema."""

    project: ProjectSettings
    paths: PathSettings = Field(default_factory=PathSettings)
    nvidia: NvidiaSettings = Field(default_factory=NvidiaSettings)
    projection: ProjectionSettings = Field(default_factory=ProjectionSettings)
    llm: LlmSettings = Field(default_factory=LlmSettings)
    eval: EvalSettings = Field(default_factory=EvalSettings)
    corpora: dict[str, CorpusEntry] = Field(default_factory=dict)
    tracking: TrackingSettings = Field(default_factory=TrackingSettings)

    def resolve(self, relative: str) -> Path:
        """Resolve a project-relative path against the repo root."""
        return PROJECT_ROOT / relative

    def runs_root(self) -> Path:
        """Return the runs directory."""
        return self.resolve(self.paths.runs_dir)


def load_config(path: Path | None = None) -> AppConfig:
    """Load and validate ``config.yaml``."""
    config_path = path or (PROJECT_ROOT / "config.yaml")
    raw: dict[str, Any] = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    return AppConfig.model_validate(raw)
