"""Tests for pipeline Layer A resume, improver skipping, and selective retry."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from rasa_skill_eval.config import AppConfig, CorpusEntry, LlmEndpointSettings, ProjectSettings
from rasa_skill_eval.models import ImproverDelta, NvidiaSkillResult
from rasa_skill_eval.pipeline import (
    _apply_delta_quality,
    _should_rewrite_skill,
    run_pipeline,
)


class _MockClient:
    """ChatClient spy recording call count."""

    def __init__(self) -> None:
        self.calls: int = 0

    def complete(self, messages: list[object], **kwargs: Any) -> Any:
        self.calls += 1
        return type("ChatResult", (), {"text": "---\nname: improved\n---\nBody"})()


def test_should_rewrite_skill_logic(tmp_path: Path) -> None:
    """_should_rewrite_skill should skip when improved file exists unless forced."""
    skill_dir = tmp_path / "improved" / "rasano" / "test-skill"
    skill_dir.mkdir(parents=True)
    skill_md = skill_dir / "SKILL.md"

    deltas = [ImproverDelta(skill_id="rasano/test-skill", degraded=True)]

    # Missing file -> rewrite
    assert _should_rewrite_skill(tmp_path, "rasano", "test-skill", deltas) is True

    # Empty file -> rewrite
    skill_md.write_text("   \n", encoding="utf-8")
    assert _should_rewrite_skill(tmp_path, "rasano", "test-skill", deltas) is True

    # Valid file with degraded delta, but retry_degraded=False -> no rewrite
    skill_md.write_text("---\nname: test-skill\n---\nImproved prose", encoding="utf-8")
    assert not _should_rewrite_skill(
        tmp_path, "rasano", "test-skill", deltas, retry_degraded=False
    )

    # Valid file with degraded delta and retry_degraded=True -> rewrite
    assert _should_rewrite_skill(
        tmp_path, "rasano", "test-skill", deltas, retry_degraded=True
    )

    # Valid file with SCHEMA HIGH in delta.changes and retry_degraded=True -> rewrite
    schema_deltas = [
        ImproverDelta(
            skill_id="rasano/test-skill",
            degraded=False,
            changes=["SCHEMA HIGH: Missing required heading: # Title"],
        )
    ]
    assert _should_rewrite_skill(
        tmp_path, "rasano", "test-skill", schema_deltas, retry_degraded=True
    )


def test_resume_skips_improver_when_improved_skill_exists(
    tmp_path: Path, monkeypatch: Any
) -> None:
    """When improved/ SKILL.md already exists, the improver is not invoked."""
    agent_dir = tmp_path / "corpus" / "rasano"
    skills_dir = agent_dir / "skills" / "block_card"
    skills_dir.mkdir(parents=True)
    (skills_dir / "skill.md").write_text(
        "---\nname: block_card\n---\nNative block card prose\n", encoding="utf-8"
    )

    run_dir = tmp_path / "run"
    improved_dir = run_dir / "improved" / "rasano" / "block-card"
    improved_dir.mkdir(parents=True)
    (improved_dir / "SKILL.md").write_text(
        "---\nname: block-card\n---\nSaved improved prose\n", encoding="utf-8"
    )

    projected_dir = run_dir / "projected" / "rasano" / "block-card"
    projected_dir.mkdir(parents=True)
    (projected_dir / "SKILL.md").write_text(
        "---\nname: block-card\n---\nProjected prose\n", encoding="utf-8"
    )

    cfg = AppConfig(
        project=ProjectSettings(rasa_pro_version="3.20.0.dev6", engine="mantle"),
        corpora={"rasano": CorpusEntry(repo="", sparse_path="", dest=str(agent_dir))},
    )

    client = _MockClient()
    monkeypatch.setattr("rasa_skill_eval.pipeline.try_client", lambda _s: client)
    monkeypatch.setattr("rasa_skill_eval.pipeline.try_backup_improver_client", lambda _s: None)
    monkeypatch.setattr(
        "rasa_skill_eval.pipeline.evaluate_skill",
        lambda *a, **k: [
            NvidiaSkillResult(
                skill_id=k.get("skill_id") or "skill",
                command="quality-check",
                quality_score=95.0,
            ),
            NvidiaSkillResult(skill_id=k.get("skill_id") or "skill", command="validate"),
        ],
    )
    monkeypatch.setattr(
        "rasa_skill_eval.pipeline.rubric_eval_skill",
        lambda *a, **k: (
            NvidiaSkillResult(
                skill_id=k.get("skill_id") or "skill",
                command="rubric-eval",
                rubric_score=90.0,
            )
        ),
    )

    from rasa_skill_eval.pipeline import merge_run_payload

    merge_run_payload(
        run_dir,
        {
            "improver": [
                {"skill_id": "rasano/block-card", "mode": "heuristic", "degraded": True}
            ],
        },
    )

    run_pipeline(
        config=cfg,
        fetch=False,
        run_dir=run_dir,
        retry_incomplete=True,
        retry_degraded=False,
    )

    assert client.calls == 0
    assert "Saved improved prose" in (improved_dir / "SKILL.md").read_text(encoding="utf-8")


def test_resume_missing_rubric_evaluates_without_reimproving(
    tmp_path: Path, monkeypatch: Any
) -> None:
    """Missing rubric-eval on an improved skill runs rubric but does not call improver."""
    agent_dir = tmp_path / "corpus" / "rasano"
    skills_dir = agent_dir / "skills" / "block_card"
    skills_dir.mkdir(parents=True)
    (skills_dir / "skill.md").write_text(
        "---\nname: block_card\n---\nNative prose\n", encoding="utf-8"
    )

    run_dir = tmp_path / "run"
    improved_dir = run_dir / "improved" / "rasano" / "block-card"
    improved_dir.mkdir(parents=True)
    (improved_dir / "SKILL.md").write_text(
        "---\nname: block-card\n---\nExisting improved\n", encoding="utf-8"
    )

    projected_dir = run_dir / "projected" / "rasano" / "block-card"
    projected_dir.mkdir(parents=True)
    (projected_dir / "SKILL.md").write_text(
        "---\nname: block-card\n---\nProjected\n", encoding="utf-8"
    )

    cfg = AppConfig(
        project=ProjectSettings(rasa_pro_version="3.20.0.dev6", engine="mantle"),
        corpora={"rasano": CorpusEntry(repo="", sparse_path="", dest=str(agent_dir))},
    )

    client = _MockClient()
    monkeypatch.setattr("rasa_skill_eval.pipeline.try_client", lambda _s: client)
    monkeypatch.setattr("rasa_skill_eval.pipeline.try_backup_improver_client", lambda _s: None)
    monkeypatch.setattr("rasa_skill_eval.pipeline.nvidia_key_configured", lambda: True)

    rubric_calls: list[str] = []
    monkeypatch.setattr(
        "rasa_skill_eval.pipeline.evaluate_skill",
        lambda *a, **k: [
            NvidiaSkillResult(
                skill_id=k.get("skill_id") or "skill",
                command="quality-check",
                quality_score=95.0,
            ),
            NvidiaSkillResult(skill_id=k.get("skill_id") or "skill", command="validate"),
        ],
    )
    monkeypatch.setattr(
        "rasa_skill_eval.pipeline.rubric_eval_skill",
        lambda *a, **k: (
            rubric_calls.append(str(k.get("skill_id"))),
            NvidiaSkillResult(
                skill_id=k.get("skill_id") or "skill",
                command="rubric-eval",
                rubric_score=85.0,
            ),
        )[1],
    )

    from rasa_skill_eval.pipeline import merge_run_payload

    merge_run_payload(
        run_dir,
        {
            "improver": [{"skill_id": "rasano/block-card", "mode": "llm", "degraded": False}],
            "nvidia": [
                {
                    "skill_id": "rasano/block-card",
                    "command": "quality-check",
                    "quality_score": 95.0,
                },
                {"skill_id": "rasano/block-card", "command": "validate"},
                {
                    "skill_id": "rasano/block-card#improved",
                    "command": "quality-check",
                    "quality_score": 98.0,
                },
                {"skill_id": "rasano/block-card#improved", "command": "validate"},
            ],
        },
    )

    run_pipeline(
        config=cfg,
        fetch=False,
        run_dir=run_dir,
        retry_incomplete=True,
        retry_degraded=False,
    )

    assert client.calls == 0
    assert len(rubric_calls) > 0
    assert "Existing improved" in (improved_dir / "SKILL.md").read_text(encoding="utf-8")


def test_retry_degraded_invokes_improver_for_degraded_skill(
    tmp_path: Path, monkeypatch: Any
) -> None:
    """When retry_degraded=True, degraded skill is rewritten by improver."""
    agent_dir = tmp_path / "corpus" / "rasano"
    skills_dir = agent_dir / "skills" / "block_card"
    skills_dir.mkdir(parents=True)
    (skills_dir / "skill.md").write_text(
        "---\nname: block_card\n---\nNative prose\n", encoding="utf-8"
    )

    run_dir = tmp_path / "run"
    improved_dir = run_dir / "improved" / "rasano" / "block-card"
    improved_dir.mkdir(parents=True)
    (improved_dir / "SKILL.md").write_text(
        "---\nname: block-card\n---\nDegraded improved prose\n", encoding="utf-8"
    )

    projected_dir = run_dir / "projected" / "rasano" / "block-card"
    projected_dir.mkdir(parents=True)
    (projected_dir / "SKILL.md").write_text(
        "---\nname: block-card\n---\nProjected prose\n", encoding="utf-8"
    )

    cfg = AppConfig(
        project=ProjectSettings(rasa_pro_version="3.20.0.dev6", engine="mantle"),
        corpora={"rasano": CorpusEntry(repo="", sparse_path="", dest=str(agent_dir))},
    )

    client = _MockClient()
    monkeypatch.setattr("rasa_skill_eval.pipeline.try_client", lambda _s: client)
    monkeypatch.setattr("rasa_skill_eval.pipeline.try_backup_improver_client", lambda _s: None)
    monkeypatch.setattr(
        "rasa_skill_eval.pipeline.evaluate_skill",
        lambda *a, **k: [
            NvidiaSkillResult(
                skill_id=k.get("skill_id") or "skill",
                command="quality-check",
                quality_score=95.0,
            ),
            NvidiaSkillResult(skill_id=k.get("skill_id") or "skill", command="validate"),
        ],
    )

    from rasa_skill_eval.pipeline import merge_run_payload

    merge_run_payload(
        run_dir,
        {
            "improver": [
                {"skill_id": "rasano/block-card", "mode": "heuristic", "degraded": True}
            ],
        },
    )

    run_pipeline(
        config=cfg,
        fetch=False,
        run_dir=run_dir,
        retry_incomplete=True,
        retry_degraded=True,
    )

    assert client.calls == 1


def test_test_pipeline_command_isolates_one_skill_and_one_model(
    tmp_path: Path, monkeypatch: Any
) -> None:
    """test_pipeline_main must select exactly one core model and one skill."""
    from rasa_skill_eval.cli import test_pipeline_main

    agent_dir = tmp_path / "corpus" / "rasano"
    for s_name in ("block_card", "check_balance"):
        s_dir = agent_dir / "skills" / s_name
        s_dir.mkdir(parents=True)
        (s_dir / "skill.md").write_text(f"---\nname: {s_name}\n---\nProse\n", encoding="utf-8")

    cfg = AppConfig(
        project=ProjectSettings(rasa_pro_version="3.20.0.dev6", engine="mantle"),
        corpora={"rasano": CorpusEntry(repo="", sparse_path="", dest=str(agent_dir))},
    )
    cfg.paths = cfg.paths.model_copy(update={"runs_dir": str(tmp_path / "runs")})
    model1 = LlmEndpointSettings(id="m1", provider="local", model="M1")
    model2 = LlmEndpointSettings(id="m2", provider="local", model="M2")
    cfg.llm.agents = [model1, model2]

    monkeypatch.setattr("rasa_skill_eval.cli.load_config", lambda: cfg)
    monkeypatch.setattr(
        "sys.argv", ["test-pipeline", "--no-fetch", "--skip-agent", "--no-progress"]
    )

    processed_skills: list[str] = []

    def mock_run_pipeline(*a: Any, **kwargs: Any) -> Path:
        only = kwargs.get("only_skill_key")
        if only:
            processed_skills.append(only)
        test_dir = kwargs["run_dir"]
        test_dir.mkdir(parents=True, exist_ok=True)
        return test_dir

    monkeypatch.setattr("rasa_skill_eval.cli.run_pipeline", mock_run_pipeline)
    monkeypatch.setattr("rasa_skill_eval.cli.finalize_report", lambda *a, **k: tmp_path)

    test_pipeline_main()

    # Only one skill was targeted
    assert len(processed_skills) == 1
    assert processed_skills[0] in ("rasano/block-card", "rasano/check-balance")
    # Config was not mutated in place
    assert len(cfg.llm.agents) == 2


def _write_skill_md(folder: Path, name: str, body: str) -> None:
    """Write a minimal SKILL.md package used by run-all2 seed tests."""
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "SKILL.md").write_text(
        f"---\nname: {name}\n---\n{body}\n",
        encoding="utf-8",
    )


def test_seed_imported_layer_a_copies_packages_not_windows_agents(tmp_path: Path) -> None:
    """Donated projected/improved packages seed a new run without coverage or agents."""
    from rasa_skill_eval.pipeline import load_run_payload, seed_imported_layer_a

    source = tmp_path / "zfiles"
    _write_skill_md(
        source / "projected" / "rasano" / "block-card",
        "block-card",
        "# Block Card\n\n## Instructions\n\nDo it.\n\n## Examples\n\nHi.",
    )
    _write_skill_md(
        source / "improved" / "rasano" / "block-card",
        "block-card",
        "# Block Card\n\n## Instructions\n\nImproved.\n\n## Examples\n\nHi.",
    )
    (source / "coverage.json").write_text("{}", encoding="utf-8")
    (source / "agents" / "rasano").mkdir(parents=True)
    (source / "results.json").write_text(
        json.dumps(
            {
                "improver": [
                    {"skill_id": "rasano/block-card", "mode": "llm", "degraded": False}
                ]
            }
        ),
        encoding="utf-8",
    )
    dest = tmp_path / "run_all2"
    deltas = seed_imported_layer_a(source, dest)
    assert deltas[0].mode == "llm"
    assert (dest / "projected" / "rasano" / "block-card" / "SKILL.md").is_file()
    assert (dest / "improved" / "rasano" / "block-card" / "SKILL.md").is_file()
    assert not (dest / "coverage.json").exists()
    assert not (dest / "agents").exists()
    payload = load_run_payload(dest)
    assert payload["meta"]["kimi_skipped"] is True
    assert payload["nvidia"] == []


def test_seed_imported_layer_a_requires_improved_skill(tmp_path: Path) -> None:
    """A donated improver row without improved SKILL.md fails before Kimi."""
    from rasa_skill_eval.pipeline import seed_imported_layer_a

    source = tmp_path / "zfiles"
    _write_skill_md(
        source / "projected" / "rasano" / "block-card",
        "block-card",
        "body",
    )
    (source / "improved" / "rasano").mkdir(parents=True)
    (source / "results.json").write_text(
        json.dumps({"improver": [{"skill_id": "rasano/block-card", "mode": "llm"}]}),
        encoding="utf-8",
    )
    try:
        seed_imported_layer_a(source, tmp_path / "dest")
    except FileNotFoundError:
        return
    raise AssertionError("expected FileNotFoundError")


def test_skip_improver_does_not_call_kimi(tmp_path: Path, monkeypatch: Any) -> None:
    """run-all2 rescoring never invokes the improver client."""
    agent_dir = tmp_path / "corpus" / "rasano"
    skills_dir = agent_dir / "skills" / "block_card"
    skills_dir.mkdir(parents=True)
    (skills_dir / "skill.md").write_text(
        "---\nname: block_card\n---\nNative prose\n", encoding="utf-8"
    )
    run_dir = tmp_path / "run"
    _write_skill_md(
        run_dir / "projected" / "rasano" / "block-card",
        "block-card",
        "# Block Card\n\n## Instructions\n\nProjected.\n\n## Examples\n\nHi.",
    )
    _write_skill_md(
        run_dir / "improved" / "rasano" / "block-card",
        "block-card",
        "# Block Card\n\n## Instructions\n\nDonated improved.\n\n## Examples\n\nHi.",
    )
    from rasa_skill_eval.pipeline import merge_run_payload

    merge_run_payload(
        run_dir,
        {"improver": [{"skill_id": "rasano/block-card", "mode": "heuristic", "degraded": False}]},
    )
    cfg = AppConfig(
        project=ProjectSettings(rasa_pro_version="3.20.0.dev6", engine="mantle"),
        corpora={"rasano": CorpusEntry(repo="", sparse_path="", dest=str(agent_dir))},
    )
    client = _MockClient()
    monkeypatch.setattr("rasa_skill_eval.pipeline.try_client", lambda _s: client)
    monkeypatch.setattr("rasa_skill_eval.pipeline.try_backup_improver_client", lambda _s: None)
    monkeypatch.setattr("rasa_skill_eval.pipeline.nvidia_key_configured", lambda: False)

    def boom(*_a: Any, **_k: Any) -> None:
        raise AssertionError("improve_projected_skill must not run")

    monkeypatch.setattr("rasa_skill_eval.pipeline.improve_projected_skill", boom)
    monkeypatch.setattr(
        "rasa_skill_eval.pipeline.evaluate_skill",
        lambda *a, **k: [
            NvidiaSkillResult(
                skill_id=k.get("skill_id") or "skill",
                command="quality-check",
                quality_score=80.0,
            ),
            NvidiaSkillResult(skill_id=k.get("skill_id") or "skill", command="validate"),
        ],
    )
    run_pipeline(
        config=cfg,
        fetch=False,
        run_dir=run_dir,
        skip_improver=True,
        preserve_projections=True,
    )
    assert client.calls == 0
    text = (run_dir / "improved" / "rasano" / "block-card" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    assert "Donated improved" in text
    assert "# Extra Projector" not in text


def test_skip_improver_fails_when_improved_missing(
    tmp_path: Path, monkeypatch: Any
) -> None:
    """Missing donated improved packages fail the skill instead of calling Kimi."""
    agent_dir = tmp_path / "corpus" / "rasano"
    skills_dir = agent_dir / "skills" / "block_card"
    skills_dir.mkdir(parents=True)
    (skills_dir / "skill.md").write_text(
        "---\nname: block_card\n---\nNative prose\n", encoding="utf-8"
    )
    run_dir = tmp_path / "run"
    _write_skill_md(
        run_dir / "projected" / "rasano" / "block-card",
        "block-card",
        "# Block Card\n\n## Instructions\n\nProjected.\n\n## Examples\n\nHi.",
    )
    cfg = AppConfig(
        project=ProjectSettings(rasa_pro_version="3.20.0.dev6", engine="mantle"),
        corpora={"rasano": CorpusEntry(repo="", sparse_path="", dest=str(agent_dir))},
    )
    improve_calls = {"n": 0}

    def boom(*_a: Any, **_k: Any) -> None:
        improve_calls["n"] += 1
        raise AssertionError("Kimi fallback is forbidden")

    monkeypatch.setattr("rasa_skill_eval.pipeline.improve_projected_skill", boom)
    monkeypatch.setattr("rasa_skill_eval.pipeline.try_client", lambda _s: _MockClient())
    monkeypatch.setattr("rasa_skill_eval.pipeline.try_backup_improver_client", lambda _s: None)
    monkeypatch.setattr("rasa_skill_eval.pipeline.nvidia_key_configured", lambda: False)
    monkeypatch.setattr(
        "rasa_skill_eval.pipeline.evaluate_skill",
        lambda *a, **k: [
            NvidiaSkillResult(
                skill_id=k.get("skill_id") or "skill",
                command="quality-check",
                quality_score=80.0,
            ),
            NvidiaSkillResult(skill_id=k.get("skill_id") or "skill", command="validate"),
        ],
    )
    run_pipeline(
        config=cfg,
        fetch=False,
        run_dir=run_dir,
        skip_improver=True,
        preserve_projections=True,
    )
    assert improve_calls["n"] == 0


def test_run_all2_main_seeds_and_skips_kimi(tmp_path: Path, monkeypatch: Any) -> None:
    """Console script run-all2 seeds Layer A from --source-run and never calls Kimi."""
    from rasa_skill_eval.cli import run_all2_main

    source = tmp_path / "zfiles"
    _write_skill_md(
        source / "projected" / "rasano" / "block-card",
        "block-card",
        "# Block Card\n\n## Instructions\n\nProjected.\n\n## Examples\n\nHi.",
    )
    _write_skill_md(
        source / "improved" / "rasano" / "block-card",
        "block-card",
        "# Block Card\n\n## Instructions\n\nImported.\n\n## Examples\n\nHi.",
    )
    (source / "coverage.json").write_text("{}", encoding="utf-8")
    (source / "results.json").write_text(
        json.dumps(
            {"improver": [{"skill_id": "rasano/block-card", "mode": "llm", "degraded": False}]}
        ),
        encoding="utf-8",
    )
    agent_dir = tmp_path / "corpus" / "rasano"
    skills_dir = agent_dir / "skills" / "block_card"
    skills_dir.mkdir(parents=True)
    (skills_dir / "skill.md").write_text(
        "---\nname: block_card\n---\nNative\n", encoding="utf-8"
    )
    cfg = AppConfig(
        project=ProjectSettings(rasa_pro_version="3.20.0.dev6", engine="mantle"),
        corpora={"rasano": CorpusEntry(repo="", sparse_path="", dest=str(agent_dir))},
    )
    cfg.paths = cfg.paths.model_copy(update={"runs_dir": str(tmp_path / "runs")})
    monkeypatch.setattr("rasa_skill_eval.cli.load_config", lambda: cfg)
    monkeypatch.setattr(
        "sys.argv",
        ["run-all2", "--no-fetch", "--skip-agent", "--no-progress", "--source-run", str(source)],
    )
    monkeypatch.setattr("rasa_skill_eval.pipeline.nvidia_key_configured", lambda: False)
    monkeypatch.setattr(
        "rasa_skill_eval.pipeline.improve_projected_skill",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("Kimi must not run")),
    )
    monkeypatch.setattr(
        "rasa_skill_eval.pipeline.evaluate_skill",
        lambda *a, **k: [
            NvidiaSkillResult(
                skill_id=k.get("skill_id") or "skill",
                command="quality-check",
                quality_score=81.0,
            ),
            NvidiaSkillResult(skill_id=k.get("skill_id") or "skill", command="validate"),
        ],
    )
    monkeypatch.setattr("rasa_skill_eval.cli.finalize_report", lambda *a, **k: tmp_path)
    run_all2_main()
    runs = list((tmp_path / "runs").glob("run_all2_*"))
    assert len(runs) == 1
    dest = runs[0]
    assert not (dest / "coverage.json").exists()
    assert "Imported" in (
        dest / "improved" / "rasano" / "block-card" / "SKILL.md"
    ).read_text(encoding="utf-8")


def test_inventory_ids_are_corpus_prefixed(tmp_path: Path, monkeypatch: Any) -> None:
    """Rasano and personalization session-start skills keep distinct inventory ids."""
    from rasa_skill_eval.pipeline import load_run_payload

    rasano = tmp_path / "corpus" / "rasano" / "skills" / "default_session_start"
    personal = tmp_path / "corpus" / "personalization" / "skills" / "default_session_start"
    for folder in (rasano, personal):
        folder.mkdir(parents=True)
        (folder / "skill.md").write_text(
            "---\nname: default_session_start\n---\nHello.\n", encoding="utf-8"
        )
    run_dir = tmp_path / "run"
    cfg = AppConfig(
        project=ProjectSettings(rasa_pro_version="3.20.0.dev6", engine="mantle"),
        corpora={
            "rasano": CorpusEntry(repo="", sparse_path="", dest=str(rasano.parents[1])),
            "personalization": CorpusEntry(
                repo="", sparse_path="", dest=str(personal.parents[1])
            ),
        },
    )
    monkeypatch.setattr("rasa_skill_eval.pipeline.try_client", lambda _s: None)
    monkeypatch.setattr("rasa_skill_eval.pipeline.try_backup_improver_client", lambda _s: None)
    monkeypatch.setattr("rasa_skill_eval.pipeline.nvidia_key_configured", lambda: False)
    monkeypatch.setattr(
        "rasa_skill_eval.pipeline.evaluate_skill",
        lambda *a, **k: [
            NvidiaSkillResult(
                skill_id=k.get("skill_id") or "skill",
                command="quality-check",
                quality_score=80.0,
            ),
            NvidiaSkillResult(skill_id=k.get("skill_id") or "skill", command="validate"),
        ],
    )
    monkeypatch.setattr(
        "rasa_skill_eval.pipeline.improve_projected_skill",
        lambda *a, **k: ImproverDelta(skill_id="x", mode="heuristic"),
    )
    run_pipeline(config=cfg, fetch=False, run_dir=run_dir)
    payload = load_run_payload(run_dir)
    ids = [row["skill_id"] for row in payload.get("inventories") or []]
    assert "rasano/default_session_start" in ids
    assert "personalization/default_session_start" in ids
    assert len(ids) == 2


def test_null_rubric_score_is_retried(tmp_path: Path, monkeypatch: Any) -> None:
    """A non-skipped rubric with a null score is incomplete and runs again."""
    agent_dir = tmp_path / "corpus" / "rasano"
    skills_dir = agent_dir / "skills" / "block_card"
    skills_dir.mkdir(parents=True)
    (skills_dir / "skill.md").write_text(
        "---\nname: block_card\n---\nNative prose\n", encoding="utf-8"
    )
    run_dir = tmp_path / "run"
    improved_dir = run_dir / "improved" / "rasano" / "block-card"
    improved_dir.mkdir(parents=True)
    (improved_dir / "SKILL.md").write_text(
        "---\nname: block-card\n---\nExisting improved\n", encoding="utf-8"
    )
    projected_dir = run_dir / "projected" / "rasano" / "block-card"
    projected_dir.mkdir(parents=True)
    (projected_dir / "SKILL.md").write_text(
        "---\nname: block-card\n---\nProjected\n", encoding="utf-8"
    )
    cfg = AppConfig(
        project=ProjectSettings(rasa_pro_version="3.20.0.dev6", engine="mantle"),
        corpora={"rasano": CorpusEntry(repo="", sparse_path="", dest=str(agent_dir))},
    )
    client = _MockClient()
    monkeypatch.setattr("rasa_skill_eval.pipeline.try_client", lambda _s: client)
    monkeypatch.setattr("rasa_skill_eval.pipeline.try_backup_improver_client", lambda _s: None)
    monkeypatch.setattr("rasa_skill_eval.pipeline.nvidia_key_configured", lambda: True)
    rubric_calls: list[str] = []
    monkeypatch.setattr(
        "rasa_skill_eval.pipeline.evaluate_skill",
        lambda *a, **k: [
            NvidiaSkillResult(
                skill_id=k.get("skill_id") or "skill",
                command="quality-check",
                quality_score=95.0,
            ),
            NvidiaSkillResult(skill_id=k.get("skill_id") or "skill", command="validate"),
        ],
    )
    monkeypatch.setattr(
        "rasa_skill_eval.pipeline.rubric_eval_skill",
        lambda *a, **k: (
            rubric_calls.append(str(k.get("skill_id"))),
            NvidiaSkillResult(
                skill_id=k.get("skill_id") or "skill",
                command="rubric-eval",
                rubric_score=88.0,
            ),
        )[1],
    )
    from rasa_skill_eval.pipeline import merge_run_payload

    merge_run_payload(
        run_dir,
        {
            "improver": [{"skill_id": "rasano/block-card", "mode": "llm", "degraded": False}],
            "nvidia": [
                {
                    "skill_id": "rasano/block-card",
                    "command": "quality-check",
                    "quality_score": 95.0,
                },
                {"skill_id": "rasano/block-card", "command": "validate"},
                {
                    "skill_id": "rasano/block-card",
                    "command": "rubric-eval",
                    "skipped": False,
                    "exit_code": 1,
                    "rubric_score": None,
                },
                {
                    "skill_id": "rasano/block-card#improved",
                    "command": "quality-check",
                    "quality_score": 98.0,
                },
                {"skill_id": "rasano/block-card#improved", "command": "validate"},
                {
                    "skill_id": "rasano/block-card#improved",
                    "command": "rubric-eval",
                    "skipped": False,
                    "exit_code": 1,
                    "rubric_score": None,
                },
            ],
        },
    )
    run_pipeline(
        config=cfg,
        fetch=False,
        run_dir=run_dir,
        retry_incomplete=True,
        retry_degraded=False,
    )
    assert client.calls == 0
    assert len(rubric_calls) >= 1
    assert "Existing improved" in (improved_dir / "SKILL.md").read_text(encoding="utf-8")


def test_apply_delta_quality_falls_back_to_hydrated_nvidia() -> None:
    """Resume with empty imp_results still reads improved quality from nvidia."""
    delta = ImproverDelta(skill_id="rasano/add-payee")
    nvidia_results = [
        NvidiaSkillResult(
            skill_id="rasano/add-payee",
            command="quality-check",
            quality_score=82.5,
        ),
        NvidiaSkillResult(
            skill_id="rasano/add-payee#improved",
            command="quality-check",
            quality_score=81.8,
        ),
    ]
    _apply_delta_quality(
        delta,
        "rasano/add-payee",
        "rasano/add-payee#improved",
        nvidia_results,
        [],
    )
    assert delta.baseline_quality == 82.5
    assert delta.improved_quality == 81.8
