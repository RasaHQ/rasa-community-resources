"""Run-directory cloning preserves the source evaluation."""

from pathlib import Path

from rasa_skill_eval.runs import clone_run_dir, latest_run_dir


def test_clone_run_dir_copies_without_editing_source(tmp_path: Path) -> None:
    """A resumed run is created as a distinct copy of its immutable source."""
    source = tmp_path / "heroes_eval_old"
    source.mkdir()
    original = source / "results.json"
    original.write_text('{"status": "old"}', encoding="utf-8")

    dest = clone_run_dir(source, tmp_path)
    (dest / "results.json").write_text('{"status": "new"}', encoding="utf-8")

    assert dest != source
    assert original.read_text(encoding="utf-8") == '{"status": "old"}'


def test_latest_run_dir_picks_newest_dated_results(tmp_path: Path) -> None:
    """Mixed prefixes sort by timestamp, and folders without results.json are ignored."""
    old = tmp_path / "run_all2_20260918_000000"
    old.mkdir()
    (old / "results.json").write_text("{}", encoding="utf-8")
    newer = tmp_path / "heroes_eval_20260919_120000"
    newer.mkdir()
    (newer / "results.json").write_text("{}", encoding="utf-8")
    hollow = tmp_path / "test_pipeline_20260920_000000"
    hollow.mkdir()
    assert latest_run_dir(tmp_path) == newer


def test_resume_missing_cli_invokes_pipeline_with_retry_flags(tmp_path: Path, monkeypatch) -> None:
    """resume-missing parses and forwards --reimprove and --retry-degraded."""
    import sys

    from rasa_skill_eval.cli import resume_missing_main
    from rasa_skill_eval.config import AppConfig, ProjectSettings

    source = tmp_path / "heroes_eval_source"
    source.mkdir()
    (source / "results.json").write_text('{"improver": []}', encoding="utf-8")

    cfg = AppConfig(
        project=ProjectSettings(rasa_pro_version="3.20.0.dev6", engine="mantle"),
        corpora={},
    )
    cfg.paths = cfg.paths.model_copy(update={"runs_dir": str(tmp_path / "runs")})

    pipeline_kwargs: dict[str, object] = {}

    def fake_run_pipeline(*args, **kwargs):
        pipeline_kwargs.update(kwargs)
        return kwargs["run_dir"]

    monkeypatch.setattr("rasa_skill_eval.cli.load_config", lambda: cfg)
    monkeypatch.setattr("rasa_skill_eval.cli.run_pipeline", fake_run_pipeline)
    monkeypatch.setattr("rasa_skill_eval.cli.run_agent_eval", lambda *a, **k: None)
    monkeypatch.setattr("rasa_skill_eval.cli.finalize_report", lambda *a, **k: None)
    monkeypatch.setattr("rasa_skill_eval.cli.incomplete_actor_ids", lambda *a, **k: [])

    # Default run: neither reimprove nor retry_degraded
    monkeypatch.setattr(
        sys, "argv", ["resume-missing", "--source-run", str(source), "--no-progress"]
    )
    resume_missing_main()
    assert pipeline_kwargs.get("reimprove") is False
    assert pipeline_kwargs.get("retry_degraded") is False
    assert pipeline_kwargs.get("retry_incomplete") is True
    assert pipeline_kwargs.get("preserve_projections") is True

    monkeypatch.setattr(
        "rasa_skill_eval.cli.clone_run_dir", lambda src, root: tmp_path / "cloned_1"
    )

    # With --retry-degraded
    monkeypatch.setattr(
        sys,
        "argv",
        ["resume-missing", "--source-run", str(source), "--no-progress", "--retry-degraded"],
    )
    resume_missing_main()
    assert pipeline_kwargs.get("retry_degraded") is True
    assert pipeline_kwargs.get("reimprove") is False

    monkeypatch.setattr(
        "rasa_skill_eval.cli.clone_run_dir", lambda src, root: tmp_path / "cloned_2"
    )

    # With --reimprove
    monkeypatch.setattr(
        sys,
        "argv",
        ["resume-missing", "--source-run", str(source), "--no-progress", "--reimprove"],
    )
    resume_missing_main()
    assert pipeline_kwargs.get("reimprove") is True
    assert pipeline_kwargs.get("preserve_projections") is False

