"""Parse SkillEvaluator quality JSON. Use overall_score, not dimension scores."""

from __future__ import annotations

import json
from pathlib import Path

from rasa_skill_eval.config import NvidiaSettings
from rasa_skill_eval.nvidia_runner import (
    _dimensions_from_obj,
    _score_from_obj,
    hydrate_nvidia_from_reports,
    nvidia_command_successful,
    parse_rubric,
    parse_schema_high,
    parse_similarity_pairs,
    skill_evaluator_env,
    stage_skill_for_evaluator,
    unique_json_file_count,
)


def test_quality_parser_prefers_overall_score() -> None:
    """Dimension scores must not shadow the composite overall_score."""
    payload = {
        "results": [
            {
                "quality": {
                    "overall_score": 82.0,
                    "grade": "B",
                    "dimensions": {"correctness": {"score": 70.0}},
                }
            }
        ]
    }
    score, grade = _score_from_obj(payload)
    assert score == 82.0
    assert grade == "B"


def test_dimension_parser_reads_nested_scores() -> None:
    """Per-category scores are exported into the metrics table."""
    payload = {
        "results": [
            {
                "quality": {
                    "overall_score": 82.0,
                    "dimensions": {
                        "correctness": {"score": 70.0},
                        "reliability": {"score": 90.0},
                    },
                }
            }
        ]
    }
    dims = _dimensions_from_obj(payload)
    assert dims["correctness"] == 70.0
    assert dims["reliability"] == 90.0


def test_unique_json_file_count_dedupes_overlapping_globs(tmp_path: Path) -> None:
    """``*.json`` plus ``**/*.json`` must not count the same file twice."""
    (tmp_path / "a.json").write_text("{}", encoding="utf-8")
    nested = tmp_path / "nested"
    nested.mkdir()
    (nested / "b.json").write_text("{}", encoding="utf-8")
    assert unique_json_file_count(tmp_path) == 2


def test_parse_schema_high_reads_nested_findings(tmp_path: Path) -> None:
    """Validate JSON SCHEMA HIGH messages are surfaced for the report."""
    (tmp_path / "validate.json").write_text(
        json.dumps(
            {
                "findings": [
                    {
                        "severity": "HIGH",
                        "category": "SCHEMA",
                        "check_name": "body_heading",
                        "message": "Missing required heading: # Title",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    assert parse_schema_high(tmp_path) == ["Missing required heading: # Title"]


def test_stage_skill_for_evaluator_uses_skills_layout(tmp_path: Path) -> None:
    """SkillEvaluator cwd is a temp tree with skills/<name>/ and no sidecar."""
    skill = tmp_path / "block-card"
    skill.mkdir()
    (skill / "SKILL.md").write_text("# Block Card\n", encoding="utf-8")
    (skill / "projection.json").write_text("{}", encoding="utf-8")
    with stage_skill_for_evaluator(skill) as (staged, root):
        assert staged == root / "skills" / "block-card"
        assert (staged / "SKILL.md").is_file()
        assert not (staged / "projection.json").exists()


def test_similarity_check_passes_type_skill(monkeypatch, tmp_path: Path) -> None:
    """Tier 2 CLI must pass ``--type skill`` so auto-detect cannot fail."""
    from rasa_skill_eval.nvidia_llm import similarity_check_collection

    captured: dict[str, object] = {}

    def fake_run(prefix: object, args: list[str], **kwargs: object) -> object:
        del prefix
        captured["args"] = args
        captured["cwd"] = kwargs.get("cwd")
        captured["extra_env"] = kwargs.get("extra_env")
        out_dir = tmp_path / "out"
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "pairs.json").write_text(
            json.dumps(
                {
                    "findings": [
                        {
                            "category": "SIMILARITY",
                            "metadata": {"entry_a": "a", "entry_b": "b"},
                        },
                        {
                            "category": "SIMILARITY",
                            "metadata": {"entry_a": "c", "entry_b": "d"},
                        },
                    ]
                }
            ),
            encoding="utf-8",
        )
        return type("Proc", (), {"returncode": 1, "stdout": "", "stderr": ""})()

    monkeypatch.setattr(
        "rasa_skill_eval.nvidia_llm.resolve_skillevaluator",
        lambda: ["skillevaluator"],
    )
    monkeypatch.setattr("rasa_skill_eval.nvidia_llm.nvidia_key_configured", lambda: True)
    monkeypatch.setattr("rasa_skill_eval.nvidia_llm._run", fake_run)
    collection = tmp_path / "rasano"
    skill = collection / "block-card"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("# Block Card\n", encoding="utf-8")
    settings = NvidiaSettings()
    result = similarity_check_collection(collection, tmp_path / "out", settings)
    args = list(captured["args"])
    assert "similarity-check" in args
    assert "--type" in args
    assert args[args.index("--type") + 1] == "skill"
    assert "--model" in args
    assert args[args.index("--model") + 1] == settings.embedding_model
    extra_env = captured["extra_env"]
    assert isinstance(extra_env, dict)
    assert extra_env["SKILL_EVAL_LLM_MODEL"] == settings.rubric_model
    assert extra_env["SKILL_EVAL_EMBEDDING_MODEL"] == settings.embedding_model
    assert result.skipped is False
    assert result.similarity_pairs == 2


def test_parse_similarity_pairs_ignores_json_file_count(tmp_path: Path) -> None:
    """A failed T2 dump is not a pair count of 1."""
    (tmp_path / "failed.json").write_text(
        json.dumps(
            {
                "overall_status": "failed",
                "total_errors": 1,
                "errors": ["model nvidia/nv-embed-v1 is end of life"],
            }
        ),
        encoding="utf-8",
    )
    assert parse_similarity_pairs(tmp_path) is None


def test_nvidia_command_successful_requires_scores() -> None:
    """A ran-but-null rubric or T2 is incomplete."""
    from rasa_skill_eval.models import NvidiaSkillResult

    hollow = NvidiaSkillResult(
        skill_id="rasano/check-balance",
        command="rubric-eval",
        skipped=False,
        exit_code=1,
        rubric_score=None,
    )
    assert nvidia_command_successful(hollow) is False
    scored = NvidiaSkillResult(
        skill_id="rasano/check-balance",
        command="rubric-eval",
        rubric_score=81.0,
        exit_code=0,
    )
    assert nvidia_command_successful(scored) is True
    below_bar = NvidiaSkillResult(
        skill_id="rasano/check-balance",
        command="rubric-eval",
        skipped=False,
        exit_code=1,
        rubric_score=46.4,
    )
    assert nvidia_command_successful(below_bar) is True
    t2 = NvidiaSkillResult(
        skill_id="rasano",
        command="similarity-check",
        skipped=False,
        exit_code=1,
        similarity_pairs=1,
    )
    assert nvidia_command_successful(t2) is True


def test_parse_rubric_reads_rubric_eval_block(tmp_path: Path) -> None:
    """SkillEvaluator writes overall_score under ``rubric_eval``, not ``rubric``."""
    (tmp_path / "skillevaluator-rubric.json").write_text(
        json.dumps(
            {
                "overall_passed": False,
                "overall_status": "failed",
                "results": [
                    {
                        "validator": "RUBRIC_EVAL",
                        "findings": [
                            {
                                "check_name": "rubric_description_clarity",
                                "metadata": {"score": 6, "id": "description_clarity"},
                            }
                        ],
                    }
                ],
                "rubric_eval": {
                    "execution_status": "succeeded",
                    "overall_score": 46.4,
                    "checks": [
                        {"id": "description_clarity", "score": 6},
                        {"id": "instruction_clarity", "score": 7},
                    ],
                },
            }
        ),
        encoding="utf-8",
    )
    score, criteria = parse_rubric(tmp_path)
    assert score == 46.4
    assert criteria["description_clarity"] == 6.0
    assert criteria["instruction_clarity"] == 7.0


def test_parse_rubric_derives_overall_from_criteria(tmp_path: Path) -> None:
    """Criterion scores still yield an overall when overall_score is null."""
    (tmp_path / "skillevaluator-rubric.json").write_text(
        json.dumps(
            {
                "results": [
                    {
                        "validator": "RUBRIC_EVAL",
                        "findings": [
                            {
                                "check_name": "rubric_description_clarity",
                                "metadata": {"score": 6, "id": "description_clarity"},
                            },
                            {
                                "check_name": "rubric_instruction_clarity",
                                "metadata": {"score": 8, "id": "instruction_clarity"},
                            },
                        ],
                    }
                ],
                "rubric_eval": {"overall_score": None, "execution_status": "failed"},
            }
        ),
        encoding="utf-8",
    )
    score, criteria = parse_rubric(tmp_path)
    assert score == 70.0
    assert criteria["description_clarity"] == 6.0
    assert criteria["instruction_clarity"] == 8.0


def test_parse_similarity_pairs_counts_nested_findings(tmp_path: Path) -> None:
    """HIGH_SIMILARITY is a pair count even when the top-level report failed."""
    (tmp_path / "skillevaluator-similarity.json").write_text(
        json.dumps(
            {
                "overall_passed": False,
                "overall_status": "failed",
                "total_errors": 1,
                "results": [
                    {
                        "validator": "Similarity Check",
                        "passed": False,
                        "status": "failed",
                        "summary": {"errors": 1, "warnings": 13},
                        "findings": [
                            {
                                "category": "SIMILARITY",
                                "check_name": "HIGH_SIMILARITY",
                                "metadata": {
                                    "entry_a": "add-payee",
                                    "entry_b": "transfer-money",
                                },
                            },
                            {
                                "category": "SIMILARITY",
                                "check_name": "SIMILAR",
                                "metadata": {
                                    "entry_a": "add-payee",
                                    "entry_b": "remove-payee",
                                },
                            },
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    assert parse_similarity_pairs(tmp_path) == 2


def test_hydrate_nvidia_from_reports_recovers_rubric_and_t2(tmp_path: Path) -> None:
    """On-disk SkillEvaluator JSON is enough to fill hollow results.json rows."""
    rubric_dir = (
        tmp_path / "nvidia" / "baseline" / "rasano" / "default-session-start" / "rubric"
    )
    rubric_dir.mkdir(parents=True)
    (rubric_dir / "skillevaluator-rubric.json").write_text(
        json.dumps(
            {
                "rubric_eval": {
                    "overall_score": 46.4,
                    "checks": [{"id": "tone", "score": 8}],
                }
            }
        ),
        encoding="utf-8",
    )
    quality_dir = (
        tmp_path / "nvidia" / "baseline" / "rasano" / "default-session-start" / "quality"
    )
    quality_dir.mkdir(parents=True)
    (quality_dir / "skillevaluator-quality.json").write_text(
        json.dumps({"quality": {"overall_score": 82.0, "grade": "B"}}),
        encoding="utf-8",
    )
    t2_dir = tmp_path / "nvidia" / "tier2" / "rasano"
    t2_dir.mkdir(parents=True)
    (t2_dir / "skillevaluator-similarity.json").write_text(
        json.dumps(
            {
                "overall_status": "failed",
                "total_errors": 1,
                "results": [
                    {
                        "findings": [
                            {
                                "category": "SIMILARITY",
                                "metadata": {"entry_a": "a", "entry_b": "b"},
                            }
                        ]
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    rows = hydrate_nvidia_from_reports(tmp_path)
    by_command = {(item.skill_id, item.command): item for item in rows}
    quality = by_command[("rasano/default-session-start", "quality-check")]
    rubric = by_command[("rasano/default-session-start", "rubric-eval")]
    t2 = by_command[("rasano", "similarity-check")]
    assert quality.quality_score == 82.0
    assert rubric.rubric_score == 46.4
    assert rubric.skipped is False
    assert t2.similarity_pairs == 1
    assert t2.skipped is False


def test_skill_evaluator_env_pins_live_models() -> None:
    """SkillEvaluator subprocesses receive Super 120B chat and nemotron embed."""
    env = skill_evaluator_env(NvidiaSettings())
    assert env["SKILL_EVAL_LLM_MODEL"] == "nvidia/nemotron-3-super-120b-a12b"
    assert env["SKILL_EVAL_EMBEDDING_MODEL"] == "nvidia/nemotron-3-embed-1b"
    openai_env = skill_evaluator_env(
        NvidiaSettings(), llm_model="gpt-4.1-mini", llm_provider="openai"
    )
    assert openai_env["SKILL_EVAL_LLM_PROVIDER"] == "openai"
    assert openai_env["SKILL_EVAL_LLM_MODEL"] == "gpt-4.1-mini"


def test_rubric_eval_retries_json_extract_with_backup(tmp_path: Path, monkeypatch) -> None:
    """JSON-extract llm_unavailable is retried with a clean dir and backup env."""
    from contextlib import contextmanager

    from rasa_skill_eval.config import LlmEndpointSettings
    from rasa_skill_eval.nvidia_llm import rubric_eval_skill

    skill = tmp_path / "projected" / "block-card"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("# Block\n", encoding="utf-8")
    output = tmp_path / "rubric"
    output.mkdir()
    envs: list[dict[str, str]] = []

    def fake_run(prefix, args, cwd, timeout, extra_env=None):
        del prefix, cwd, timeout
        out_dir = Path(args[args.index("-o") + 1])
        env = dict(extra_env or {})
        envs.append(env)
        if env.get("SKILL_EVAL_LLM_PROVIDER") == "openai":
            (out_dir / "skillevaluator-rubric.json").write_text(
                json.dumps({"rubric_eval": {"overall_score": 81.0, "checks": []}}),
                encoding="utf-8",
            )
            stdout = "json report: ok\n"
        else:
            (out_dir / "skillevaluator-rubric.json").write_text(
                json.dumps(
                    {
                        "results": [
                            {
                                "findings": [
                                    {
                                        "check_name": "llm_unavailable",
                                        "message": "LLM judge unavailable",
                                    }
                                ]
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            stdout = (
                "WARNING  LLM call failed (Could not extract valid JSON from LLM "
                "response (15864 chars): line 1 column 1 (char 0))\n"
            )
        return type("Proc", (), {"returncode": 1, "stdout": stdout, "stderr": "Error\n"})()

    @contextmanager
    def fake_stage(projected_dir):
        yield projected_dir, projected_dir

    monkeypatch.setattr(
        "rasa_skill_eval.nvidia_llm.resolve_skillevaluator", lambda: ["skillevaluator"]
    )
    monkeypatch.setattr("rasa_skill_eval.nvidia_llm.nvidia_key_configured", lambda: True)
    monkeypatch.setattr("rasa_skill_eval.nvidia_llm._run", fake_run)
    monkeypatch.setattr(
        "rasa_skill_eval.nvidia_llm.stage_skill_for_evaluator", fake_stage
    )
    result = rubric_eval_skill(
        skill,
        output,
        NvidiaSettings(),
        skill_id="rasano/block-card",
        judge=LlmEndpointSettings(
            provider="nvidia",
            backup_provider="openai",
            backup_model="gpt-4.1-mini",
        ),
    )
    assert len(envs) == 2
    assert envs[1]["SKILL_EVAL_LLM_PROVIDER"] == "openai"
    assert envs[1]["SKILL_EVAL_LLM_MODEL"] == "gpt-4.1-mini"
    assert result.skipped is False
    assert result.rubric_score == 81.0

