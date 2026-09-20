"""Durable progress state remains accurate across updates and resumes."""

import json
from pathlib import Path

from rasa_skill_eval.models import ProgressUnit
from rasa_skill_eval.progress import ProgressManager


def test_progress_manager_counts_only_complete_as_done(tmp_path: Path) -> None:
    """Failed and skipped units stay out of the percent-complete numerator."""
    manager = ProgressManager(tmp_path)
    manager.plan(
        [
            ProgressUnit(key="skill:a", phase="layer_a"),
            ProgressUnit(key="skill:b", phase="layer_a"),
            ProgressUnit(key="skill:c", phase="layer_a"),
        ]
    )
    manager.mark("skill:a", "layer_a", "complete")
    manager.mark("skill:b", "layer_a", "failed", reason="timeout")
    manager.mark("skill:c", "layer_a", "skipped")

    payload = json.loads((tmp_path / "progress.json").read_text(encoding="utf-8"))
    assert payload["layer_a"] == {"done": 1, "total": 3, "pct": 33.3}
    assert payload["units"]["skill:b"]["details"]["reason"] == "timeout"


def test_progress_manager_loads_existing_manifest(tmp_path: Path) -> None:
    """A resumed manager retains completed work from its prior snapshot."""
    manager = ProgressManager(tmp_path)
    manager.mark("scenario:a", "layer_b", "complete")

    resumed = ProgressManager(tmp_path)

    assert resumed.state.units["scenario:a"].status == "complete"
    assert resumed.state.layer_b["done"] == 1


def test_seed_from_run_requires_quality_scores_and_llm_metrics(tmp_path: Path) -> None:
    """Hollow NVIDIA quality and tool_correctness-only DeepEval stay pending."""
    from rasa_skill_eval.config import (
        AppConfig,
        CorpusEntry,
        LlmEndpointSettings,
        LlmSettings,
        ProjectSettings,
    )

    agent_dir = tmp_path / "corpus" / "rasano"
    skill_dir = agent_dir / "skills" / "block_card"
    skill_dir.mkdir(parents=True)
    (skill_dir / "skill.md").write_text("---\nname: block_card\n---\nProse\n", encoding="utf-8")
    (tmp_path / "results.json").write_text(
        json.dumps(
            {
                "improver": [{"skill_id": "rasano/block-card"}],
                "nvidia": [
                    {
                        "skill_id": "rasano/block-card",
                        "command": "quality-check",
                        "skipped": False,
                        "quality_score": None,
                    },
                    {
                        "skill_id": "rasano/block-card#improved",
                        "command": "quality-check",
                        "skipped": False,
                        "quality_score": None,
                    },
                ],
                "tsr": [
                    {
                        "agent_id": "rasano",
                        "model_id": "lfm-1.2b",
                        "arm": "native",
                        "scenario_id": "faq",
                        "repeat": 0,
                        "skipped": False,
                    }
                ],
                "deepeval": [
                    {
                        "agent_id": "rasano",
                        "model_id": "lfm-1.2b",
                        "arm": "native",
                        "scenario_id": "faq",
                        "repeat": 0,
                        "metric": "tool_correctness",
                        "score": 1.0,
                        "skipped": False,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    scenario_dir = tmp_path / "eval" / "scenarios" / "rasano"
    scenario_dir.mkdir(parents=True)
    (scenario_dir / "faq.yml").write_text(
        "id: faq\nagent: rasano\nexpect:\n  skill_started: banking_faq\n",
        encoding="utf-8",
    )
    cfg = AppConfig(
        project=ProjectSettings(rasa_pro_version="3.20.0.dev6", engine="mantle"),
        corpora={"rasano": CorpusEntry(repo="", sparse_path="", dest=str(agent_dir))},
        llm=LlmSettings(
            agents=[LlmEndpointSettings(id="lfm-1.2b", provider="local", model="x")]
        ),
    )
    cfg.eval.repeats = 1
    manager = ProgressManager(tmp_path)
    manager.seed_from_run(cfg)
    assert manager.state.units["skill:rasano/block-card"].status == "pending"
    deep_units = [unit for unit in manager.state.units.values() if unit.phase == "deepeval"]
    assert deep_units
    assert all(unit.status == "pending" for unit in deep_units)


def test_seed_from_run_requires_rubric_when_key_configured(tmp_path: Path, monkeypatch) -> None:
    """Quality plus validate is not Layer A complete while rubric scores are missing."""
    from rasa_skill_eval.config import (
        AppConfig,
        CorpusEntry,
        LlmEndpointSettings,
        LlmSettings,
        ProjectSettings,
    )

    monkeypatch.setattr("rasa_skill_eval.progress.nvidia_key_configured", lambda: True)
    agent_dir = tmp_path / "corpus" / "rasano"
    skill_dir = agent_dir / "skills" / "block_card"
    skill_dir.mkdir(parents=True)
    (skill_dir / "skill.md").write_text("---\nname: block_card\n---\nProse\n", encoding="utf-8")
    nvidia_rows = []
    for skill_id in ("rasano/block-card", "rasano/block-card#improved"):
        nvidia_rows.extend(
            [
                {
                    "skill_id": skill_id,
                    "command": "quality-check",
                    "skipped": False,
                    "quality_score": 80.0,
                },
                {
                    "skill_id": skill_id,
                    "command": "validate",
                    "skipped": False,
                },
                {
                    "skill_id": skill_id,
                    "command": "rubric-eval",
                    "skipped": True,
                    "rubric_score": None,
                },
            ]
        )
    (tmp_path / "results.json").write_text(
        json.dumps({"improver": [{"skill_id": "rasano/block-card"}], "nvidia": nvidia_rows}),
        encoding="utf-8",
    )
    cfg = AppConfig(
        project=ProjectSettings(rasa_pro_version="3.20.0.dev6", engine="mantle"),
        corpora={"rasano": CorpusEntry(repo="", sparse_path="", dest=str(agent_dir))},
        llm=LlmSettings(
            agents=[LlmEndpointSettings(id="lfm-1.2b", provider="local", model="x")]
        ),
    )
    cfg.eval.repeats = 1
    manager = ProgressManager(tmp_path)
    manager.mark("skill:rasano/block-card", "layer_a", "complete")
    manager.seed_from_run(cfg)
    assert manager.state.units["skill:rasano/block-card"].status == "pending"
