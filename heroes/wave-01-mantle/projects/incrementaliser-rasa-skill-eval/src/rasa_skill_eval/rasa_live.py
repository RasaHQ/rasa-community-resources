"""Start a trained Rasano copy and replay scenario turns over the REST channel."""

from __future__ import annotations

import socket
import subprocess
import time
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx
from loguru import logger

from rasa_skill_eval.models import ObservedTrace
from rasa_skill_eval.proc import Deadline, kill_process_tree
from rasa_skill_eval.tracker_parse import observation_from_tracker

_TURN_LOG_CHARS = 80


def truncate_user_text(text: str, limit: int = _TURN_LOG_CHARS) -> str:
    """Collapse whitespace and cap length for a one-line turn log."""
    collapsed = " ".join(str(text).split())
    if len(collapsed) <= limit:
        return collapsed
    keep = max(0, limit - 3)
    return collapsed[:keep] + "..."


def free_port() -> int:
    """Bind port 0 and return the OS-assigned free port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class RasaRestServer:
    """``rasa run --enable-api`` subprocess for one agent copy."""

    def __init__(
        self,
        agent_root: Path,
        *,
        env: dict[str, str] | None = None,
        startup_timeout_sec: float = 180.0,
        turn_timeout_sec: float = 180.0,
        scenario_timeout_sec: float = 360.0,
    ) -> None:
        """Store paths and timeouts. ``start`` launches the process."""
        self.agent_root = agent_root
        self.env = env
        self.startup_timeout_sec = startup_timeout_sec
        self.turn_timeout_sec = turn_timeout_sec
        self.scenario_timeout_sec = scenario_timeout_sec
        self.port = free_port()
        self.base_url = f"http://127.0.0.1:{self.port}"
        self._proc: subprocess.Popen[str] | None = None
        self._log_file: Any = None

    def start(self) -> None:
        """Launch ``uv run rasa run`` and wait until the API answers."""
        log_path = self.agent_root / "rasa_run.log"
        self._log_file = log_path.open("w", encoding="utf-8")
        self._proc = subprocess.Popen(
            [
                "uv",
                "run",
                "rasa",
                "run",
                "--enable-api",
                "--cors",
                "*",
                "--connector",
                "rest",
                "-p",
                str(self.port),
                "--response-timeout",
                str(int(self.turn_timeout_sec)),
            ],
            cwd=self.agent_root,
            stdout=self._log_file,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=self.env,
        )
        deadline = Deadline(self.startup_timeout_sec)
        last_error = "server did not become ready"
        while not deadline.expired():
            if self._proc.poll() is not None:
                tail = _tail(log_path)
                raise RuntimeError(f"rasa run exited {self._proc.returncode}: {tail}")
            try:
                response = httpx.get(
                    f"{self.base_url}/status",
                    timeout=min(2.0, max(0.2, deadline.remaining())),
                )
                if response.status_code < 500:
                    logger.info("Rasa API ready on {}", self.base_url)
                    return
            except httpx.HTTPError as exc:
                last_error = str(exc)
            time.sleep(min(1.0, max(0.1, deadline.remaining())))
        raise TimeoutError(f"rasa run not ready on {self.base_url}: {last_error}")

    def stop(self) -> None:
        """Kill ``uv run rasa`` and its grandchildren, then close the log."""
        if self._proc is not None:
            kill_process_tree(self._proc)
            logger.info("Stopped Rasa API on {}", self.base_url)
            self._proc = None
        if self._log_file is not None:
            self._log_file.close()
            self._log_file = None

    def healthy(self) -> bool:
        """Return True when the REST status endpoint answers without a 5xx."""
        if self._proc is None or self._proc.poll() is not None:
            return False
        try:
            response = httpx.get(f"{self.base_url}/status", timeout=2.0)
        except httpx.HTTPError:
            return False
        return response.status_code < 500

    def restart(self) -> None:
        """Stop and start a new Rasa API on a fresh port."""
        self.stop()
        self.port = free_port()
        self.base_url = f"http://127.0.0.1:{self.port}"
        self.start()

    def run_turns(self, turns: list[dict[str, Any]], sender_id: str) -> ObservedTrace:
        """POST each user turn, then load the conversation tracker."""
        deadline = Deadline(self.scenario_timeout_sec)
        started = time.perf_counter()
        for turn in turns:
            user = turn.get("user") if isinstance(turn, dict) else None
            if not user:
                continue
            remaining = deadline.remaining()
            if remaining <= 0:
                raise TimeoutError("scenario timed out before all turns completed")
            logger.info("POST {} turn: {}", self.base_url, truncate_user_text(str(user)))
            response = httpx.post(
                f"{self.base_url}/webhooks/rest/webhook",
                json={"sender": sender_id, "message": str(user)},
                timeout=min(self.turn_timeout_sec, remaining),
            )
            response.raise_for_status()
        remaining = deadline.remaining()
        if remaining <= 0:
            raise TimeoutError("scenario timed out before tracker fetch")
        tracker = self._fetch_tracker(sender_id, timeout=min(self.turn_timeout_sec, remaining))
        observed = observation_from_tracker(tracker)
        return observed.model_copy(update={"latency_sec": time.perf_counter() - started})

    def _fetch_tracker(self, sender_id: str, timeout: float | None = None) -> dict[str, Any]:
        """Return the tracker JSON for ``sender_id``."""
        response = httpx.get(
            f"{self.base_url}/conversations/{sender_id}/tracker",
            timeout=self.turn_timeout_sec if timeout is None else timeout,
        )
        response.raise_for_status()
        payload = response.json()
        return payload if isinstance(payload, dict) else {}


def run_scenario_live(
    server: RasaRestServer,
    spec: dict[str, Any],
) -> ObservedTrace:
    """Replay one scenario spec against a running server."""
    turns = spec.get("turns") if isinstance(spec.get("turns"), list) else []
    sender = f"{spec.get('id', 'scenario')}-{uuid4().hex[:8]}"
    return server.run_turns(turns, sender)


def _tail(path: Path, n: int = 800) -> str:
    """Return the last ``n`` characters of a log file."""
    if not path.is_file():
        return ""
    text = path.read_text(encoding="utf-8", errors="replace")
    return text[-n:]
