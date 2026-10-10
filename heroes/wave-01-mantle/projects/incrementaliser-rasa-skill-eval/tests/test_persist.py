"""Process-tree kill on interrupt and incremental results.json."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from rasa_skill_eval.models import TsrRun
from rasa_skill_eval.persist import upsert_tsr
from rasa_skill_eval.pipeline import load_run_payload, merge_run_payload
from rasa_skill_eval.proc import CommandTimeout, run_captured


class _InterruptPopen:
    """Popen stand-in whose communicate raises KeyboardInterrupt."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        del args, kwargs
        self.pid = 4242

    def communicate(self, timeout: float | None = None) -> tuple[str, str]:
        """Simulate Ctrl+C while waiting on the child."""
        del timeout
        raise KeyboardInterrupt

    def poll(self) -> int | None:
        """Still running."""
        return None

    def wait(self, timeout: float | None = None) -> int:
        """Pretend the kill succeeded."""
        del timeout
        return 1

    def kill(self) -> None:
        """No-op kill."""
        return None

    def terminate(self) -> None:
        """No-op terminate."""
        return None


def test_run_captured_kills_tree_on_interrupt(monkeypatch) -> None:
    """KeyboardInterrupt must kill the child before it propagates."""
    killed: dict[str, list[str]] = {}

    def fake_run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        del kwargs
        killed["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr("rasa_skill_eval.proc.subprocess.Popen", _InterruptPopen)
    monkeypatch.setattr("rasa_skill_eval.proc.subprocess.run", fake_run)
    monkeypatch.setattr("rasa_skill_eval.proc.sys.platform", "win32")
    with pytest.raises(KeyboardInterrupt):
        run_captured(["uv", "sync"], cwd=Path("."))
    assert killed["cmd"][:3] == ["taskkill", "/F", "/T"]
    assert killed["cmd"][-1] == "4242"


def test_eval_all_finalizes_on_interrupt(monkeypatch, tmp_path: Path) -> None:
    """Ctrl+C during Layer B still runs finalize_report."""
    called = {"finalize": 0}

    monkeypatch.setattr("rasa_skill_eval.cli.run_pipeline", lambda **_k: tmp_path)

    def boom(**_k: object) -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr("rasa_skill_eval.cli.run_agent_eval", boom)

    def fin(**_k: object) -> Path:
        called["finalize"] += 1
        return tmp_path

    monkeypatch.setattr("rasa_skill_eval.cli.finalize_report", fin)
    monkeypatch.setattr(
        "sys.argv",
        ["eval-all", "--no-fetch", "--run-dir", str(tmp_path)],
    )
    with pytest.raises(KeyboardInterrupt):
        from rasa_skill_eval.cli import eval_all_main

        eval_all_main()
    assert called["finalize"] == 1


def test_merge_run_payload_keeps_layer_a_and_merges_meta(tmp_path: Path) -> None:
    """Layer B flush must not drop inventories; meta keys merge."""
    merge_run_payload(
        tmp_path,
        {"inventories": [{"skill_id": "x"}], "meta": {"engine": "mantle"}},
    )
    merge_run_payload(
        tmp_path,
        {"tsr": [{"scenario_id": "s"}], "meta": {"interrupted": True}},
    )
    payload = load_run_payload(tmp_path)
    assert payload["inventories"][0]["skill_id"] == "x"
    assert payload["tsr"][0]["scenario_id"] == "s"
    assert payload["meta"]["engine"] == "mantle"
    assert payload["meta"]["interrupted"] is True


def test_merge_run_payload_is_atomic(tmp_path: Path) -> None:
    """results.json is replaced via a temp file."""
    merge_run_payload(tmp_path, {"tsr": []})
    assert (tmp_path / "results.json").is_file()
    assert not (tmp_path / "results.json.tmp").is_file()


def test_upsert_tsr_replaces_same_identity() -> None:
    """Resume must replace a scenario-repeat instead of duplicating it."""
    first = TsrRun(scenario_id="s", arm="native", repeat=0, skipped=True, skip_reason="old")
    second = TsrRun(scenario_id="s", arm="native", repeat=0, skipped=False, weighted=1.0)
    merged = upsert_tsr([first], [second])
    assert len(merged) == 1
    assert merged[0].weighted == 1.0
    assert merged[0].skipped is False


class _TimeoutPopen:
    """Popen stand-in whose communicate raises TimeoutExpired."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        del args, kwargs
        self.pid = 99
        self.returncode = None

    def communicate(self, timeout: float | None = None) -> tuple[str, str]:
        """Pretend the child hung past the deadline."""
        raise subprocess.TimeoutExpired(["uv"], timeout or 1)

    def poll(self) -> int | None:
        """Still running."""
        return None

    def wait(self, timeout: float | None = None) -> int:
        """Pretend the kill succeeded."""
        del timeout
        return 1

    def kill(self) -> None:
        """No-op kill."""
        return None

    def terminate(self) -> None:
        """No-op terminate."""
        return None


def test_run_captured_kills_tree_on_timeout(monkeypatch, tmp_path: Path) -> None:
    """A hung uv/rasa child is killed when timeout_sec elapses."""
    killed: dict[str, list[str]] = {}

    def fake_run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        del kwargs
        killed["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr("rasa_skill_eval.proc.subprocess.Popen", _TimeoutPopen)
    monkeypatch.setattr("rasa_skill_eval.proc.subprocess.run", fake_run)
    monkeypatch.setattr("rasa_skill_eval.proc.sys.platform", "win32")
    with pytest.raises(CommandTimeout):
        run_captured(["uv", "sync"], cwd=tmp_path, timeout_sec=1)
    assert killed["cmd"][:3] == ["taskkill", "/F", "/T"]


def test_run_captured_streams_log_file(tmp_path: Path) -> None:
    """Stage logs must be written while the child runs, not only after exit."""
    log_path = tmp_path / "sync.log"
    proc = run_captured(["uv", "--version"], cwd=tmp_path, log_path=log_path, timeout_sec=30)
    assert log_path.is_file()
    text = log_path.read_text(encoding="utf-8")
    assert "uv" in text.lower() or proc.returncode == 0


def test_improver_mode_label_uses_actual_deltas() -> None:
    """Metadata must not claim llm when every rewrite fell back."""
    from rasa_skill_eval.models import ImproverDelta
    from rasa_skill_eval.persist import improver_mode_label

    deltas = [
        ImproverDelta(skill_id="a", mode="heuristic", degraded=True),
        ImproverDelta(skill_id="b", mode="heuristic", degraded=True),
    ]
    assert improver_mode_label(deltas, client_available=True) == "heuristic"


def test_pipeline_removes_log_sink(monkeypatch, tmp_path: Path) -> None:
    """Layer A must not leave a loguru sink behind after return."""
    from loguru import logger

    from rasa_skill_eval.config import AppConfig, ProjectSettings
    from rasa_skill_eval.pipeline import run_pipeline

    before = len(logger._core.handlers)
    cfg = AppConfig(
        project=ProjectSettings(rasa_pro_version="3.20.0.dev6", engine="mantle"),
        corpora={},
    )
    monkeypatch.setattr("rasa_skill_eval.pipeline.try_client", lambda _s: None)
    run_pipeline(config=cfg, fetch=False, run_dir=tmp_path)
    assert len(logger._core.handlers) == before
