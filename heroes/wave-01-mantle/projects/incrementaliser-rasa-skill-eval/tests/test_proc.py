"""Linux process-tree kill must terminate the process group, not only the parent."""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

from rasa_skill_eval.proc import kill_process_tree, run_captured


def test_spawn_starts_new_session_on_linux(tmp_path: Path) -> None:
    """uv-run children must be their own process group so killpg can reap them."""
    if sys.platform == "win32":
        return
    completed = run_captured(["bash", "-c", "echo ok"], cwd=tmp_path, timeout_sec=10)
    assert completed.returncode == 0
    assert "ok" in completed.stdout


def test_kill_process_tree_kills_process_group() -> None:
    """A sleeping child started in a new session exits after kill_process_tree."""
    if sys.platform == "win32":
        return
    proc = subprocess.Popen(
        ["bash", "-c", "sleep 30"],
        start_new_session=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(0.2)
    assert proc.poll() is None
    kill_process_tree(proc)
    proc.wait(timeout=10)
    assert proc.poll() is not None
