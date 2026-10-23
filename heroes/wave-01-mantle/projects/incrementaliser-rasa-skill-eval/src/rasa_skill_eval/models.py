"""Pydantic models for inventories, projections, scopes, findings, and TSR."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class FindingSeverity(StrEnum):
    """Severity for Mantle-native static findings."""

    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class FindingClass(StrEnum):
    """Heroes report classification for a finding."""

    SPEC_MISMATCH = "spec_mismatch"
    PORTABLE_AUTHORING = "portable_authoring"
    MANTLE_ONLY = "mantle_only"


class SkillScope(StrEnum):
    """Where a skill or its dependencies live."""

    SKILL_LOCAL = "skill-local"
    PROJECT_GLOBAL = "project-global"
    ENGINE_MANAGED = "engine-managed"
    CODING_AGENT_LOCAL = "coding-agent-local"
    CODING_AGENT_GLOBAL = "coding-agent-global"


class Finding(BaseModel):
    """One static check result."""

    code: str
    message: str
    severity: FindingSeverity
    finding_class: FindingClass
    skill_id: str


class ToolConstraintInfo(BaseModel):
    """Parsed ``tool_constraints`` entry."""

    tool_name: str
    requires: str | None = None
    requires_confirmation: bool = False
    on_success: str | None = None
    on_failure: str | None = None


class MantleInventory(BaseModel):
    """Native Mantle skill inventory. NVIDIA cannot see most of this."""

    skill_id: str
    display_name: str
    description: str
    source_path: str
    extra_frontmatter_keys: list[str] = Field(default_factory=list)
    import_tools: list[str] = Field(default_factory=list)
    tool_constraints: list[ToolConstraintInfo] = Field(default_factory=list)
    if_conditions: list[str] = Field(default_factory=list)
    ordered_block_ids: list[str] = Field(default_factory=list)
    skill_refs: list[str] = Field(default_factory=list)
    memory_refs: list[str] = Field(default_factory=list)
    has_local_tools: bool = False
    has_memory_yml: bool = False
    has_responses_yml: bool = False
    has_references: bool = False
    body_line_count: int = 0
    irreversible_without_confirmation: list[str] = Field(default_factory=list)
    project_memory_fields: list[str] = Field(default_factory=list)
    llm_settable_project_fields: list[str] = Field(default_factory=list)
    voice_enabled: bool = False
    voice_one_question: bool = False
    scopes: list[SkillScope] = Field(default_factory=list)
    findings: list[Finding] = Field(default_factory=list)
    frontmatter: dict[str, Any] = Field(default_factory=dict)
    body: str = ""


class ProjectionSidecar(BaseModel):
    """Record of fields rewritten when projecting to Agent Skills."""

    source_skill_id: str
    source_display_name: str
    projected_name: str
    source_path: str
    projected_path: str
    rewritten_fields: list[str] = Field(default_factory=list)
    moved_frontmatter: list[str] = Field(default_factory=list)
    copied_files: list[str] = Field(default_factory=list)


class NvidiaSkillResult(BaseModel):
    """Captured SkillEvaluator invocation for one projected skill."""

    skill_id: str
    command: str
    exit_code: int | None = None
    skipped: bool = False
    skip_reason: str | None = None
    stdout: str = ""
    stderr: str = ""
    report_files: list[str] = Field(default_factory=list)
    quality_score: float | None = None
    quality_grade: str | None = None
    dimensions: dict[str, float] = Field(default_factory=dict)
    rubric_score: float | None = None
    rubric_criteria: dict[str, float] = Field(default_factory=dict)
    skill_lift: float | None = None
    pass_at_k: float | None = None
    similarity_pairs: int | None = None
    schema_high: list[str] = Field(default_factory=list)


class ImproverDelta(BaseModel):
    """Before/after metrics for one projected skill."""

    skill_id: str
    baseline_quality: float | None = None
    improved_quality: float | None = None
    baseline_skill_md_words: int = 0
    improved_skill_md_words: int = 0
    constraints_preserved: bool = True
    changes: list[str] = Field(default_factory=list)
    mode: str = "failed"
    degraded: bool = False
    source_hash: str = ""
    mantle_yml_match: bool | None = None


class IntegrationIssue(BaseModel):
    """A Mantle or rasa-pro failure the harness observed at train or run time.

    Scores are the instrument; these rows are the bugs the eval exists to find.
    ``report_upstream`` marks engine issues (file with Rasa). Harness failures
    such as NVIDIA 429 stay ``False``.
    """

    code: str
    message: str
    agent_id: str = ""
    model_id: str = ""
    arm: str = ""
    skill_id: str | None = None
    event: str = ""
    source: str = "rasa_train"
    report_upstream: bool = True
    suggested_ask: str = ""
    workaround_applied: str | None = None
    workaround_succeeded: bool | None = None
    raw: str = ""


class TsrComponents(BaseModel):
    """Per-run component scores. None means inapplicable (dropped from TSR)."""

    skill_started: float | None = None
    tool_correct: float | None = None
    memory_set: float | None = None
    confirmation: float | None = None
    safety: float | None = None

    def as_dict(self) -> dict[str, float | None]:
        """Return component name to score-or-None."""
        return {
            "skill_started": self.skill_started,
            "tool_correct": self.tool_correct,
            "memory_set": self.memory_set,
            "confirmation": self.confirmation,
            "safety": self.safety,
        }


class TsrRun(BaseModel):
    """One scenario repeat on one agent arm for one agent-core model."""

    scenario_id: str
    skill: str | None = None
    arm: str
    repeat: int
    agent_id: str = "rasano"
    model_id: str = "default"
    components: TsrComponents = Field(default_factory=TsrComponents)
    weighted: float = 0.0
    strict: bool = False
    tokens: int | None = None
    latency_sec: float | None = None
    skipped: bool = False
    skip_reason: str | None = None
    notes: str = ""
    source: str = ""
    source_path: str | None = None


class DeepEvalResult(BaseModel):
    """One DeepEval metric on one transcript."""

    scenario_id: str
    arm: str
    metric: str
    score: float | None = None
    skipped: bool = False
    skip_reason: str | None = None
    reason: str = ""
    agent_id: str = ""
    model_id: str = ""
    repeat: int = 0
    judge_model: str = ""


class ObservedEvent(BaseModel):
    """One tracker event kept for ordered TSR assertions."""

    kind: str
    name: str = ""
    index: int = 0
    arguments: dict[str, Any] = Field(default_factory=dict)


class ObservedTrace(BaseModel):
    """What a scenario runner saw. Used by weighted TSR."""

    skills_started: list[str] = Field(default_factory=list)
    tools_called: list[str] = Field(default_factory=list)
    memory_set: dict[str, str] = Field(default_factory=dict)
    confirmation_seen: bool | None = None
    forbidden_tools_called: list[str] = Field(default_factory=list)
    bot_text: str = ""
    tokens: int | None = None
    latency_sec: float | None = None
    events: list[ObservedEvent] = Field(default_factory=list)
    tool_arguments: list[dict[str, Any]] = Field(default_factory=list)
    source: str = "live"
    source_path: str | None = None


class CoverageUnit(BaseModel):
    """One planned Layer B unit (actor or agent/model/arm)."""

    kind: str
    key: str
    status: str = "pending"
    reason: str | None = None
    pid: int | None = None
    log_path: str | None = None
    model_id: str = ""
    agent_id: str = ""
    arm: str = ""


class ProgressUnit(BaseModel):
    """One durable unit of work shown by local and remote progress views."""

    key: str
    phase: str
    status: str = "pending"
    details: dict[str, Any] = Field(default_factory=dict)


class ProgressState(BaseModel):
    """Resume-aware progress snapshot for one evaluation run."""

    run_id: str
    started_at: str
    updated_at: str
    overall_pct: float = 0.0
    layer_a: dict[str, int | float] = Field(default_factory=dict)
    layer_b: dict[str, int | float] = Field(default_factory=dict)
    deepeval: dict[str, int | float] = Field(default_factory=dict)
    finalize: dict[str, int | float] = Field(default_factory=dict)
    units: dict[str, ProgressUnit] = Field(default_factory=dict)
