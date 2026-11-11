"""Rasa REST server stop must kill the Windows process tree."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from rasa_skill_eval.rasa_live import RasaRestServer, truncate_user_text


class _AlivePopen:
    """Popen stand-in that still looks running."""

    pid = 5555

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


def test_truncate_user_text_collapses_whitespace() -> None:
    """Turn logs stay on one line."""
    assert truncate_user_text("  hello\n  world  ") == "hello world"


def test_truncate_user_text_caps_length() -> None:
    """Long user text is clipped with an ellipsis inside the limit."""
    out = truncate_user_text("a" * 100, limit=20)
    assert out.endswith("...")
    assert len(out) == 20


def test_rasa_rest_server_stop_kills_tree(monkeypatch, tmp_path: Path) -> None:
    """Windows stop must ``taskkill /T`` the uv rasa tree, not only terminate uv."""
    killed: dict[str, list[str]] = {}

    def fake_run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        del kwargs
        killed["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr("rasa_skill_eval.proc.subprocess.run", fake_run)
    monkeypatch.setattr("rasa_skill_eval.proc.sys.platform", "win32")
    server = RasaRestServer(tmp_path)
    server._proc = _AlivePopen()  # type: ignore[assignment]
    log_path = tmp_path / "rasa_run.log"
    server._log_file = log_path.open("w", encoding="utf-8")
    server.stop()
    assert killed["cmd"][:3] == ["taskkill", "/F", "/T"]
    assert killed["cmd"][-1] == "5555"
    assert server._proc is None
    assert server._log_file is None


def test_run_turns_enforces_scenario_deadline(tmp_path: Path) -> None:
    """A zero scenario budget fails before the first HTTP turn."""
    server = RasaRestServer(tmp_path, scenario_timeout_sec=0.0, turn_timeout_sec=30.0)
    with pytest.raises(TimeoutError, match="scenario timed out"):
        server.run_turns([{"user": "hi"}], "sender")
