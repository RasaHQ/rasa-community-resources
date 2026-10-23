"""Subprocess helpers that kill the child tree on interrupt or timeout."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any, TextIO


class CommandTimeout(TimeoutError):
    """A captured command exceeded its deadline."""


class Deadline:
    """Expire when either monotonic or wall-clock elapsed time exceeds the budget.

    Wall time catches host sleep/hibernation when ``monotonic`` does not jump.
    """

    def __init__(
        self,
        timeout_sec: float,
        *,
        monotonic_fn: Callable[[], float] | None = None,
        wall_fn: Callable[[], float] | None = None,
    ) -> None:
        """Start a dual-clock deadline of ``timeout_sec`` seconds."""
        self.timeout_sec = float(timeout_sec)
        self._monotonic = monotonic_fn or time.monotonic
        self._wall = wall_fn or time.time
        self.mono_start = self._monotonic()
        self.wall_start = self._wall()

    def remaining(self) -> float:
        """Seconds left on the tighter of the two clocks."""
        mono_left = self.mono_start + self.timeout_sec - self._monotonic()
        wall_left = self.wall_start + self.timeout_sec - self._wall()
        return max(0.0, min(mono_left, wall_left))

    def expired(self) -> bool:
        """True when the budget is exhausted."""
        return self.remaining() <= 0.0


def run_captured(
    command: list[str],
    *,
    cwd: Path,
    env: dict[str, str] | None = None,
    timeout_sec: float | None = None,
    log_path: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run ``command``, capturing stdout/stderr as text.

    On ``KeyboardInterrupt`` or timeout the process tree is killed before the
    error propagates, so ``uv`` / ``rasa`` children do not keep running.
    When ``log_path`` is set, output is streamed there and the returned
    stdout is the file tail.
    """
    log_file: TextIO | None = None
    kwargs: dict[str, Any] = {
        "cwd": cwd,
        "env": env,
        "text": True,
        "encoding": "utf-8",
        "errors": "replace",
    }
    if log_path is not None:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_file = log_path.open("w", encoding="utf-8")
        kwargs["stdout"] = log_file
        kwargs["stderr"] = subprocess.STDOUT
    else:
        kwargs["stdout"] = subprocess.PIPE
        kwargs["stderr"] = subprocess.PIPE
    if sys.platform == "win32":
        # CREATE_NEW_PROCESS_GROUP exists only on Windows; tests may monkeypatch
        # sys.platform while still running on Linux.
        kwargs["creationflags"] = int(
            getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200)
        )
    else:
        kwargs["start_new_session"] = True
    proc = subprocess.Popen(command, **kwargs)
    try:
        try:
            stdout, stderr = proc.communicate(timeout=timeout_sec)
        except subprocess.TimeoutExpired as exc:
            kill_process_tree(proc)
            tail = _log_tail(log_path)
            raise CommandTimeout(
                f"{command[0]} timed out after {timeout_sec}s: {tail or command}"
            ) from exc
        except KeyboardInterrupt:
            kill_process_tree(proc)
            raise
    finally:
        if log_file is not None:
            log_file.close()
    if log_path is not None:
        tail = _log_tail(log_path)
        return subprocess.CompletedProcess(command, proc.returncode, tail, "")
    return subprocess.CompletedProcess(
        command, proc.returncode, stdout or "", stderr or ""
    )


def kill_process_tree(proc: subprocess.Popen[Any]) -> None:
    """Terminate ``proc`` and its descendants. No-op if it has already exited."""
    if proc.poll() is not None:
        return
    if sys.platform == "win32":
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
            capture_output=True,
            check=False,
        )
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
        return
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except (ProcessLookupError, PermissionError, OSError):
        proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError, OSError):
            proc.kill()


def _log_tail(path: Path | None, n: int = 4000) -> str:
    """Return the last ``n`` characters of a log file."""
    if path is None or not path.is_file():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")[-n:]
