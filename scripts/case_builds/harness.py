"""Shared harness for casebook case builds: start an agent, drive scripted
conversations, save trackers, measure latency and usage, check outcomes.

Stdlib only, like the rest of scripts/: it runs under a bare `python3`. The one
piece that runs inside the agent's own virtualenv is usage_launcher.py, which
the server is started through.

A build is a Mantle project with a `case-build/conversations.json` spec. See
scripts/case_builds/README.md for the spec format and the driver contract a
voice driver has to meet.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import signal
import socket
import statistics
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Optional

SCRIPTS = Path(__file__).resolve().parent.parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from check_project import _load_dotenv  # noqa: E402
from rasa_projects import REPO_ROOT  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
import voice_driver  # noqa: E402

LAUNCHER = Path(__file__).resolve().parent / "usage_launcher.py"
SPEC_DIR = "case-build"
SPEC_FILE = "conversations.json"

# Engine-internal tools Mantle offers the model for routing and memory. They
# appear in the tracker next to domain tools; checks name them explicitly when
# they matter and ignore them otherwise.
ENGINE_TOOLS = frozenset(
    {
        # rasa.mantle's built-in tool names on the pinned engine.
        "activate",
        "cancel_skill",
        "cannot_help",
        "complete_skill",
        "correct",
        "hangup",
        "listen",
        "record_discovered_facts",
        "resolve_tool_confirmation",
        "search_knowledge",
        "set_fields",
    }
)


# ----------------------------------------------------------------------------
# Agent server lifecycle
# ----------------------------------------------------------------------------


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def agent_env(project: Path, extra: Optional[dict] = None) -> dict:
    """Environment for the agent process: exports, then project .env, then root .env.

    Values are loaded into the child's environment only and never printed.
    """
    before = dict(os.environ)
    _load_dotenv(project)
    env = dict(os.environ)
    os.environ.clear()
    os.environ.update(before)
    env.setdefault("RASA_TELEMETRY_ENABLED", "false")
    env.update(extra or {})
    return env


class AgentServer:
    """`rasa train` and `rasa run --enable-api` for one project, through uv."""

    def __init__(self, project: Path, workdir: Path, *, price_model: Optional[str] = None,
                 port: Optional[int] = None) -> None:
        self.project = project
        self.workdir = workdir
        self.port = port or _free_port()
        self.base_url = f"http://127.0.0.1:{self.port}"
        self.usage_log = workdir / "usage.jsonl"
        self.server_log = workdir / "server.log"
        self.proc: Optional[subprocess.Popen] = None
        self.env = agent_env(
            project,
            {
                "CASE_BUILD_USAGE_LOG": str(self.usage_log),
                "CASE_BUILD_PRICE_MODEL": price_model or "",
                # Price from LiteLLM's bundled map, not a live fetch, so a
                # rerun prices against the same table.
                "LITELLM_LOCAL_MODEL_COST_MAP": "True",
                # Exposes GET /conversations/<id>/engine_tokens, Rasa's own
                # per-conversation token total, used as a cross-check.
                "RASA_FEATURE_FLAG_SIM_EVAL_EXTENDED": "true",
            },
        )

    def _uv(self) -> str:
        uv = shutil.which("uv")
        if not uv:
            raise RuntimeError("uv not found on PATH")
        return uv

    def train(self) -> float:
        started = time.monotonic()
        with open(self.workdir / "train.log", "w", encoding="utf-8") as log:
            subprocess.run(
                [self._uv(), "run", "--locked", "rasa", "train"],
                cwd=self.project, env=self.env, check=True, stdout=log, stderr=subprocess.STDOUT,
            )
        return time.monotonic() - started

    def start(self, timeout: float = 240.0) -> None:
        self.usage_log.touch()
        log = open(self.server_log, "w", encoding="utf-8")
        self.proc = subprocess.Popen(
            [self._uv(), "run", "--locked", "python", str(LAUNCHER),
             "run", "--enable-api", "-p", str(self.port), "-i", "127.0.0.1"],
            cwd=self.project, env=self.env, stdout=log, stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.proc.poll() is not None:
                raise RuntimeError(f"agent exited during startup; see {self.server_log}")
            try:
                status = http_json("GET", f"{self.base_url}/status", timeout=3)
                if status.get("model_file"):
                    self.model_file = status["model_file"]
                    return
            except (urllib.error.URLError, OSError, ValueError):
                pass
            time.sleep(1.5)
        self.stop()
        raise RuntimeError(f"agent did not become ready in {timeout}s; see {self.server_log}")

    def stop(self) -> None:
        if self.proc and self.proc.poll() is None:
            os.killpg(self.proc.pid, signal.SIGINT)
            try:
                self.proc.wait(timeout=20)
            except subprocess.TimeoutExpired:
                os.killpg(self.proc.pid, signal.SIGKILL)
        self.proc = None

    def tracker(self, conversation_id: str) -> dict:
        return http_json("GET", f"{self.base_url}/conversations/{conversation_id}/tracker")

    def engine_tokens(self, conversation_id: str) -> Optional[dict]:
        try:
            return http_json("GET", f"{self.base_url}/conversations/{conversation_id}/engine_tokens")
        except (urllib.error.URLError, ValueError):
            return None

    def __enter__(self) -> "AgentServer":
        self.start()
        return self

    def __exit__(self, *exc: Any) -> None:
        self.stop()


def http_json(method: str, url: str, payload: Any = None, timeout: float = 180.0) -> Any:
    data = None if payload is None else json.dumps(payload).encode()
    request = urllib.request.Request(url, data=data, method=method,
                                     headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = response.read()
    return json.loads(body) if body else None


# ----------------------------------------------------------------------------
# Drivers
# ----------------------------------------------------------------------------


@dataclass
class TurnObservation:
    """What a driver measured for one caller turn.

    `latency_ms` is the caller-perceived wait the driver defines. For REST it
    is request sent to full response received. A voice driver defines it as
    end of caller speech to first bot audio, and puts its component timings
    (ASR final, first TTS byte and so on) in `extra`.
    """

    user_text: str
    bot_messages: list[dict]
    latency_ms: float
    started_at: float
    extra: dict = field(default_factory=dict)


class Driver:
    """One conversation over one channel. Subclass per channel.

    The harness calls start(), then send() once per scripted turn, then
    finish(). `conversation_id` must be the tracker sender id the channel
    used, because trackers, usage and log events are joined on it.
    """

    channel = "abstract"

    def start(self, conversation_id: str) -> None:
        self.conversation_id = conversation_id

    def send(self, turn: dict) -> TurnObservation:
        raise NotImplementedError

    def finish(self) -> None:
        pass


class RestDriver(Driver):
    """Web chat over Rasa's REST channel (POST /webhooks/rest/webhook)."""

    channel = "rest"

    def __init__(self, base_url: str, timeout: float = 180.0, **_: Any) -> None:
        self.base_url = base_url
        self.timeout = timeout

    def send(self, turn: dict) -> TurnObservation:
        started_wall = time.time()
        started = time.perf_counter()
        messages = http_json(
            "POST",
            f"{self.base_url}/webhooks/rest/webhook",
            {"sender": self.conversation_id, "message": turn["user"]},
            timeout=self.timeout,
        )
        latency_ms = (time.perf_counter() - started) * 1000
        return TurnObservation(turn["user"], messages or [], latency_ms, started_wall)


class BrowserAudioDriver(Driver):
    """Voice over Rasa's browser_audio WebSocket channel (voice_driver.py).

    Each turn streams the turn's pre-rendered caller WAV (`turn["audio"]`,
    relative to the spec's `voice.caller_audio_dir`) in real time, or in
    `text` mode sends `{"text": turn["user"]}`, which skips speech-to-text but
    still bills the model and text-to-speech. `latency_ms` is end of caller
    speech to the first bot audio frame with sound in it; the driver also
    records the end-marker latency figures, what the tracker heard, and
    Mantle's latency_breakdown for the turn.
    """

    channel = "browser_audio"

    def __init__(self, base_url: str, *, spec: Optional[dict] = None, project: Optional[Path] = None,
                 mode: Optional[str] = None, **_: Any) -> None:
        voice = (spec or {}).get("voice", {})
        self.base_url = base_url
        self.ws_url = base_url.replace("http://", "ws://", 1) + voice.get(
            "path", "/webhooks/browser_audio/websocket")
        self.mode = mode or voice.get("mode", "audio")
        if self.mode not in ("audio", "text"):
            raise ValueError(f"unknown voice mode {self.mode!r}")
        self.audio_dir = (project or Path(".")) / voice.get("caller_audio_dir", "case-build/caller-audio")
        self.sender_header = voice.get("sender_header", voice_driver.DEFAULT_SENDER_HEADER)
        self.prompt_ack = bool(voice.get("prompt_marker_ack", False))
        self.turn_timeout_s = float(voice.get("turn_timeout_s", 90))
        self.default_voice = (voice.get("caller") or {}).get("voice", "")
        self.call_stats: dict = {}

    def _fetch_tracker(self, sender_id: str) -> dict:
        return http_json("GET", f"{self.base_url}/conversations/{sender_id}/tracker", timeout=10)

    def start(self, conversation_id: str) -> None:
        super().start(conversation_id)
        self.call_stats = {}
        self.call = voice_driver.BrowserAudioCall(
            self.ws_url, conversation_id, sender_header=self.sender_header,
            fetch_tracker=self._fetch_tracker, prompt_ack=self.prompt_ack,
            turn_timeout_s=self.turn_timeout_s,
        )
        self.greeting = self.call.open()

    def send(self, turn: dict) -> TurnObservation:
        started_wall = time.time()
        if self.mode == "text":
            result = self.call.say(text=turn["user"])
        else:
            name = voice_driver.turn_audio_name(turn, self.default_voice)
            pcm, rate = voice_driver.load_pcm16(self.audio_dir / name)
            if rate != self.call.rate:
                raise ValueError(f"{name} is {rate} Hz; the channel handshake asked for {self.call.rate} Hz")
            result = self.call.say(pcm=pcm)
        if result["voice"]["ended_by"] in ("timeout", "closed") and not result["bot_messages"]:
            raise RuntimeError(f"no bot turn after caller turn ({result['voice']['ended_by']})")
        return TurnObservation(turn["user"], result["bot_messages"], result["latency_ms"], started_wall,
                               extra=result["voice"])

    def finish(self) -> None:
        call = getattr(self, "call", None)
        if call is not None and getattr(call, "ws", None) is not None:
            self.call_stats = {**call.close(), "mode": self.mode, **(self.greeting or {})} \
                if hasattr(self, "greeting") else call.close()
            self.call_stats["session_end_turn_s"] = self._wait_session_end_turn()
        self.call = None
        self.greeting = None

    def _wait_session_end_turn(self, timeout: float = 30.0) -> Optional[float]:
        """Wait for the model turn Mantle runs on /session_end after a hangup.

        Mantle answers the caller's hangup with a full turn (model calls
        included) that nobody hears. Waiting for its bot_turn_ended keeps
        those calls attributed to this conversation. Returns the seconds it
        took, or None if it did not finish in time.
        """
        started = time.monotonic()
        while time.monotonic() - started < timeout:
            try:
                events = self._fetch_tracker(self.conversation_id).get("events", [])
            except Exception:
                events = []
            ends = [i for i, e in enumerate(events) if e.get("event") == "user" and e.get("text") == "/session_end"]
            if ends and any(e.get("event") == "bot_turn_ended" for e in events[ends[-1]:]):
                return round(time.monotonic() - started, 2)
            time.sleep(0.5)
        return None


DRIVERS = {"rest": RestDriver, "browser_audio": BrowserAudioDriver}


# ----------------------------------------------------------------------------
# Tracker reading and checks
# ----------------------------------------------------------------------------


def _parse_result(raw: Any) -> Any:
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except ValueError:
            return raw
    return raw


def tool_events(tracker: dict) -> list[dict]:
    """Tool calls in tracker order, with the index of the user turn they followed."""
    calls: list[dict] = []
    user_turn = -1
    for event in tracker.get("events", []):
        kind = event.get("event")
        if kind == "user":
            user_turn += 1
        elif kind == "tool_executed":
            calls.append(
                {
                    "tool": event.get("tool_name"),
                    "arguments": event.get("arguments") or {},
                    "result": _parse_result(event.get("result")),
                    "is_error": bool(event.get("is_error")),
                    "source": (event.get("metadata") or {}).get("source") or "llm",
                    "after_user_turn": user_turn,
                }
            )
    return calls


def bot_events(tracker: dict) -> list[dict]:
    bots = []
    user_turn = -1
    for event in tracker.get("events", []):
        if event.get("event") == "user":
            user_turn += 1
        elif event.get("event") == "bot":
            meta = event.get("metadata") or {}
            bots.append(
                {
                    "text": event.get("text") or "",
                    "source": meta.get("mantle_response_source"),
                    "utter_action": meta.get("utter_action"),
                    "llm_total_time_ms": meta.get("llm_total_time_ms"),
                    "after_user_turn": user_turn,
                }
            )
    return bots


def _norm(value: Any) -> Any:
    if isinstance(value, str):
        return re.sub(r"\s+", " ", value.strip()).upper()
    return value


def matches(expected: Any, actual: Any) -> bool:
    """Subset match. Dicts match on the listed keys; strings case-insensitively.

    A string starting with `re:` is a regular expression searched
    case-insensitively; `{"any": [...]}` matches if any alternative does.
    """
    if isinstance(expected, dict) and set(expected) == {"any"}:
        return any(matches(option, actual) for option in expected["any"])
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(
            key in actual and matches(value, actual[key]) for key, value in expected.items()
        )
    if isinstance(expected, str) and expected.startswith("re:"):
        return actual is not None and re.search(expected[3:], str(actual), re.IGNORECASE) is not None
    if expected is None:
        return actual is None
    return _norm(expected) == _norm(actual)


def _select(calls: Iterable[dict], check: dict) -> list[dict]:
    selected = []
    for call in calls:
        if check.get("tool", "*") not in ("*", call["tool"]):
            continue
        if "args" in check and not matches(check["args"], call["arguments"]):
            continue
        if "result" in check and not matches(check["result"], call["result"]):
            continue
        if "after_user_turn" in check and call["after_user_turn"] < check["after_user_turn"]:
            continue
        selected.append(call)
    return selected


def evaluate_check(check: dict, tracker: dict) -> tuple[bool, str]:
    calls = tool_events(tracker)
    kind = check["type"]
    if kind == "tool_called":
        hits = _select(calls, check)
        need = check.get("min", 1)
        return len(hits) >= need, f"{len(hits)} matching call(s), need >= {need}"
    if kind == "tool_not_called":
        hits = _select(calls, check)
        return not hits, f"{len(hits)} forbidden matching call(s)"
    if kind == "tool_order":
        position = -1
        for step in check["steps"]:
            found = [i for i, call in enumerate(calls) if i > position and _select([call], step)]
            if not found:
                return False, f"no {step.get('tool')} call after position {position}"
            position = found[0]
        return True, "calls occurred in order"
    if kind == "any_of":
        outcomes = [evaluate_check(option, tracker) for option in check["checks"]]
        passed = any(ok for ok, _ in outcomes)
        return passed, "; ".join(detail for _, detail in outcomes)
    if kind == "no_tool_errors":
        errors = [c["tool"] for c in calls if c["is_error"]]
        return not errors, f"tool errors: {errors}" if errors else "no tool errors"
    raise ValueError(f"unknown check type {kind!r}")


_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")


def text_metric_hits(metric: Any, text: str) -> list[str]:
    """Matches of a bot-text metric in one message.

    A metric is a regex string, or {"pattern": ..., "unless_before": ...}: a
    match is ignored when `unless_before` matches earlier in the same sentence
    (a negation or hedge such as "whether this loss is covered").
    """
    if isinstance(metric, str):
        metric = {"pattern": metric}
    pattern = re.compile(metric["pattern"], re.IGNORECASE)
    hedge = re.compile(metric["unless_before"], re.IGNORECASE) if metric.get("unless_before") else None
    hits = []
    for sentence in _SENTENCE_RE.split(text or ""):
        for match in pattern.finditer(sentence):
            if hedge is None or not hedge.search(sentence[: match.start()]):
                hits.append(match.group(0))
    return hits


# ----------------------------------------------------------------------------
# Usage and log attribution
# ----------------------------------------------------------------------------


def read_jsonl(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                rows.append(json.loads(line))
            except ValueError:
                continue
    return rows


def usage_for(rows: list[dict], conversation_id: str) -> dict:
    calls = [r for r in rows if r.get("kind") == "llm_call" and r.get("sender_id") == conversation_id]
    total = lambda key: sum((c.get(key) or 0) for c in calls)  # noqa: E731
    costs = [c.get("response_cost_usd") for c in calls]
    priced = all(isinstance(c, (int, float)) for c in costs)
    return {
        "llm_calls": len(calls),
        "main_loop_calls": sum(c.get("sender_source") == "turn_context" for c in calls),
        "side_channel_calls": sum(c.get("sender_source") != "turn_context" for c in calls),
        "failed_calls": sum(not c.get("ok") for c in calls),
        "prompt_tokens": total("prompt_tokens"),
        "completion_tokens": total("completion_tokens"),
        "reasoning_tokens": total("reasoning_tokens"),
        "cached_prompt_tokens": total("cached_prompt_tokens"),
        "cost_usd": round(sum(costs), 6) if calls and priced else (0.0 if not calls else None),
        "cost_complete": priced,
        "request_thought_signatures": total("request_thought_signatures"),
        "request_placeholder_signatures": total("request_placeholder_signatures"),
        "empty_completions": sum(
            1 for c in calls if c.get("ok") and not c.get("completion_tokens")
        ),
        "llm_latency_ms": [round(c["latency_ms"], 1) for c in calls if c.get("latency_ms") is not None],
    }


LOG_JSON_RE = re.compile(r"(\{.*\})\s*$")


def log_events_for(server_log: Path, conversation_id: str, names: Iterable[str]) -> dict:
    """Count structured server-log events for one conversation, by event name."""
    wanted = set(names)
    counts: dict[str, list[dict]] = {name: [] for name in wanted}
    if not wanted or not server_log.is_file():
        return counts
    for line in server_log.read_text(encoding="utf-8", errors="replace").splitlines():
        match = LOG_JSON_RE.search(line)
        if not match:
            continue
        try:
            record = json.loads(match.group(1))
        except ValueError:
            continue
        if record.get("event") in wanted and (
            record.get("sender_id") == conversation_id
            or record.get("conversation_id") == conversation_id
        ):
            counts[record["event"]].append(
                {k: v for k, v in record.items() if k not in ("level", "event")}
            )
    return counts


# ----------------------------------------------------------------------------
# Spend ledger and budget
# ----------------------------------------------------------------------------


def ledger_path(project: Path) -> Path:
    return project / SPEC_DIR / "results" / "spend-ledger.json"


def ledger_total(project: Path) -> float:
    path = ledger_path(project)
    if not path.is_file():
        return 0.0
    return round(sum(run.get("cost_usd") or 0 for run in json.loads(path.read_text())["runs"]), 6)


def ledger_append(project: Path, entry: dict) -> None:
    path = ledger_path(project)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.loads(path.read_text()) if path.is_file() else {"runs": []}
    data["runs"].append(entry)
    data["total_cost_usd"] = round(sum(r.get("cost_usd") or 0 for r in data["runs"]), 6)
    path.write_text(json.dumps(data, indent=2) + "\n")


# ----------------------------------------------------------------------------
# Running a spec
# ----------------------------------------------------------------------------


def percentile(values: list[float], pct: float) -> Optional[float]:
    """Nearest-rank percentile; None for an empty list."""
    if not values:
        return None
    ordered = sorted(values)
    rank = max(1, int(-(-pct * len(ordered) // 100)))
    return round(ordered[min(rank, len(ordered)) - 1], 1)


def load_spec(project: Path) -> dict:
    return json.loads((project / SPEC_DIR / SPEC_FILE).read_text(encoding="utf-8"))


def classify(error: Optional[str], checks: list[dict], usage: dict) -> str:
    """pass, fail, or provider_error when a model call failed (quota, outage).

    A provider error is not evidence about the agent: Mantle answers a failed
    call with a canned apology, so its checks fail for a reason unrelated to
    the behaviour under test. It is reported separately and never as a pass.
    """
    if usage.get("failed_calls"):
        return "provider_error"
    if error is None and all(c["passed"] for c in checks):
        return "pass"
    return "fail"


def run_conversation(server: AgentServer, driver: Driver, spec: dict, conv: dict,
                     run_tag: str, out_dir: Path) -> dict:
    conversation_id = f"{spec['build']}-{conv['id']}-{run_tag}"
    turns: list[dict] = []
    error = None
    try:
        driver.start(conversation_id)
        for turn in conv["turns"]:
            observation = driver.send(turn)
            turns.append(
                {
                    "user": observation.user_text,
                    "latency_ms": None if observation.latency_ms is None else round(observation.latency_ms, 1),
                    "bot": [m.get("text") for m in observation.bot_messages if m.get("text")],
                    **({"extra": observation.extra} if observation.extra else {}),
                }
            )
    except Exception as exc:  # recorded, never hidden
        error = f"{type(exc).__name__}: {exc}"
    finally:
        try:
            driver.finish()
        except Exception as exc:
            error = error or f"{type(exc).__name__} on finish: {exc}"

    # Side-channel calls (fact discovery) finish after the reply; give them
    # a moment to land in the usage log before attribution.
    time.sleep(spec.get("settle_seconds", 4))
    tracker = server.tracker(conversation_id)
    (out_dir / "trackers").mkdir(parents=True, exist_ok=True)
    (out_dir / "trackers" / f"{conv['id']}.json").write_text(json.dumps(tracker, indent=1) + "\n")

    checks = []
    for check in conv["checks"]:
        try:
            passed, detail = evaluate_check(check, tracker)
        except Exception as exc:
            passed, detail = False, f"check error: {exc}"
        checks.append({"check": check, "passed": passed, "detail": detail})

    bots = bot_events(tracker)
    metrics: dict[str, Any] = {
        "filler_messages": [b["text"] for b in bots if b["source"] == "filler"],
    }
    for name, metric in (spec.get("bot_text_metrics") or {}).items():
        metrics[name] = [
            b["text"] for b in bots if b["source"] != "verbatim" and text_metric_hits(metric, b["text"])
        ]
    for name, spec_metric in (spec.get("tool_result_metrics") or {}).items():
        metrics[name] = tool_result_metric(spec_metric, tracker)
    rows = read_jsonl(server.usage_log)
    usage = usage_for(rows, conversation_id)
    logs = log_events_for(server.server_log, conversation_id, spec.get("log_events", []))
    voice = voice_report(spec, conv, turns, tracker, getattr(driver, "call_stats", None)) \
        if driver.channel == "browser_audio" else None
    return {
        "id": conv["id"],
        "kind": conv.get("kind"),
        "description": conv.get("description"),
        "conversation_id": conversation_id,
        "passed": error is None and all(c["passed"] for c in checks),
        "outcome": classify(error, checks, usage),
        "error": error,
        "turns": turns,
        "checks": checks,
        "tool_calls": [
            {k: c[k] for k in ("tool", "arguments", "after_user_turn", "is_error", "source")}
            | {"result_status": c["result"].get("status") if isinstance(c["result"], dict) else None,
               "result_reason": c["result"].get("reason") if isinstance(c["result"], dict) else None}
            for c in tool_events(tracker)
            if c["tool"] not in ENGINE_TOOLS
        ],
        "engine_tool_calls": [c["tool"] for c in tool_events(tracker) if c["tool"] in ENGINE_TOOLS],
        "metrics": metrics,
        "log_events": {name: len(items) for name, items in logs.items()},
        "log_event_details": logs,
        "usage": usage,
        **({"voice": voice} if voice is not None else {}),
        "engine_tokens": server.engine_tokens(conversation_id),
    }


# ----------------------------------------------------------------------------
# Voice: speech usage, speech cost and what speech-to-text heard
# ----------------------------------------------------------------------------


def speech_cost(pricing: dict, stt_seconds: float, tts_characters: int) -> dict:
    """Speech spend from the spec's published per-unit prices; None when unpriced."""
    stt = (pricing or {}).get("stt") or {}
    tts = (pricing or {}).get("tts") or {}
    stt_usd = None if stt.get("usd_per_minute") is None else round(stt_seconds / 60 * stt["usd_per_minute"], 6)
    tts_usd = None if tts.get("usd_per_1k_characters") is None else round(
        tts_characters / 1000 * tts["usd_per_1k_characters"], 6)
    return {
        "stt_usd": stt_usd,
        "tts_usd": tts_usd,
        "cost_usd": None if stt_usd is None or tts_usd is None else round(stt_usd + tts_usd, 6),
    }


def voice_report(spec: dict, conv: dict, turns: list[dict], tracker: dict, call_stats: Optional[dict]) -> dict:
    """Per-conversation speech usage, speech cost and speech-to-text accuracy.

    Speech-to-text is billed on every second of audio streamed to it, and the
    channel forwards the caller's continuous stream, silence included, so the
    billed seconds are the seconds the driver sent. Text-to-speech is counted
    as the characters of every bot message in the tracker. Rasa's in-process
    TTS cache can serve a repeated text without a vendor call, so this is an
    upper bound.
    """
    stats = call_stats or {}
    for observed in turns:
        extra = observed.get("extra") or {}
        if extra.get("end_markers"):
            extra["end_markers"] = voice_driver.dedupe_latency_markers(extra["end_markers"])
    stt_seconds = float(stats.get("audio_seconds_sent") or 0)
    tts_characters = sum(len(b["text"]) for b in bot_events(tracker))
    asr = []
    for spec_turn, observed in zip(conv["turns"], turns):
        extra = observed.get("extra") or {}
        if extra.get("mode") != "audio" or observed.get("user") != spec_turn["user"]:
            # Text turns skip speech-to-text; a turn whose script line has
            # changed since the run cannot be checked against the new line.
            continue
        heard_parts = [h for h in extra.get("heard") or [] if h]
        heard = " ".join(heard_parts)
        asr.append({
            "intended": spec_turn["user"],
            "heard": heard_parts,
            "user_events": len(extra.get("heard") or []),
            "wer": voice_driver.word_error_rate(spec_turn["user"], heard),
            "tokens": voice_driver.check_tokens(heard, spec_turn.get("asr_tokens", [])),
        })
    return {
        "mode": stats.get("mode"),
        "stt_audio_seconds": round(stt_seconds, 2),
        "tts_characters": tts_characters,
        "call": stats,
        **speech_cost(spec.get("speech_pricing") or {}, stt_seconds, tts_characters),
        "asr": asr,
    }


def tool_result_metric(metric: dict, tracker: dict) -> dict:
    """Sum of one numeric result field over a tool's calls that report it.

    For the case metric, e.g. {"tool": "block_card", "field":
    "unselected_cards_changed"}: the numerator summed over block attempts.
    """
    values = [
        c["result"].get(metric["field"])
        for c in tool_events(tracker)
        if c["tool"] == metric["tool"] and isinstance(c["result"], dict)
        and isinstance(c["result"].get(metric["field"]), (int, float))
    ]
    return {"attempts": len(values), "total": sum(values)}


def run_speech_cost(results: list[dict]) -> float:
    return round(sum(((r.get("voice") or {}).get("cost_usd") or 0) for r in results), 6)


def _pcts(values: list) -> dict:
    values = [v for v in values if isinstance(v, (int, float))]
    return {"n": len(values), "p50": percentile(values, 50), "p95": percentile(values, 95),
            "max": round(max(values), 1) if values else None}


def aggregate_voice(results: list[dict]) -> Optional[dict]:
    """Voice figures across a run: latency parts, speech usage, ASR accuracy."""
    voiced = [r for r in results if r.get("voice")]
    if not voiced:
        return None
    turns = [t.get("extra") or {} for r in voiced for t in r["turns"]]
    audio_turns = [t for t in turns if t.get("mode") == "audio"]
    first_end = [t["end_markers"][0] for t in turns if t.get("end_markers")]
    breakdowns = [b for t in turns for b in (t.get("latency_breakdown") or [])[:1] if b]

    def bd(path: str) -> list:
        out = []
        for b in breakdowns:
            value: Any = b
            for key in path.split("."):
                value = value.get(key) if isinstance(value, dict) else None
            out.append(value)
        return out

    tokens = [tok for r in voiced for a in r["voice"]["asr"] for tok in a["tokens"]]
    by_kind: dict[str, dict] = {}
    for tok in tokens:
        k = by_kind.setdefault(tok["kind"], {"checked": 0, "exact": 0, "normalised": 0})
        k["checked"] += 1
        k["exact"] += tok["exact"]
        k["normalised"] += tok["normalised"]
    asr_turns = [a for r in voiced for a in r["voice"]["asr"]]
    wers = [a["wer"] for a in asr_turns if a["wer"] is not None]
    unpriced = any(r["voice"].get("cost_usd") is None for r in voiced)
    return {
        "turns": len(turns),
        "audio_turns": len(audio_turns),
        "eos_to_first_audible_ms": _pcts([t.get("eos_to_first_audible_ms") for t in turns]),
        "eos_to_first_audio_ms": _pcts([t.get("eos_to_first_audio_ms") for t in turns]),
        "eos_to_first_marker_ms": _pcts([t.get("eos_to_first_marker_ms") for t in turns]),
        "end_marker_first_message": {
            key: _pcts([m.get(key) for m in first_end])
            for key in ("rasa_processing_latency_ms", "tts_first_byte_latency_ms", "tts_complete_latency_ms")
        },
        "latency_breakdown_first": {
            "turns_with_breakdown": len(breakdowns),
            **{path: _pcts(bd(path)) for path in (
                "user_perceived_latency_ms",
                "llm_generation_before_first_output_ms",
                "first_agent_response.llm_time_to_first_token_ms",
                "first_agent_response.llm_total_generation_ms",
                "first_voice_response.tts_time_to_first_byte_ms",
                "first_voice_response.tts_total_generation_ms",
            )},
        },
        "turns_ended_by": {k: sum(t.get("ended_by") == k for t in turns)
                           for k in ("tracker", "quiet_window", "timeout", "closed")},
        "interrupts": sum(t.get("interrupts") or 0 for t in turns),
        "asr": {
            "turns_checked": len(asr_turns),
            "turns_heard_nothing": sum(a["user_events"] == 0 for a in asr_turns),
            "turns_split": sum(a["user_events"] > 1 for a in asr_turns),
            "wer_mean": round(statistics.fmean(wers), 3) if wers else None,
            "wer_p50": percentile(wers, 50) if wers else None,
            "tokens": by_kind,
        },
        "stt_audio_seconds": round(sum(r["voice"]["stt_audio_seconds"] for r in voiced), 1),
        "tts_characters": sum(r["voice"]["tts_characters"] for r in voiced),
        "stt_usd": round(sum(r["voice"].get("stt_usd") or 0 for r in voiced), 6),
        "tts_usd": round(sum(r["voice"].get("tts_usd") or 0 for r in voiced), 6),
        "speech_cost_usd": run_speech_cost(voiced),
        "speech_cost_complete": not unpriced,
    }


def usage_log_cost(path: Path) -> float:
    """Every priced call in a run's usage log, attributed or not."""
    return round(
        sum((r.get("response_cost_usd") or 0) for r in read_jsonl(path) if r.get("kind") == "llm_call"), 6
    )


def _raise_exit(signum: int, _frame: Any) -> None:
    raise SystemExit(128 + signum)


def aggregate(results: list[dict], spec: dict) -> dict:
    """Summary figures derived only from per-conversation results."""
    latencies = [t["latency_ms"] for r in results for t in r["turns"] if t["latency_ms"] is not None]
    usage_total = lambda key: sum(r["usage"].get(key, 0) or 0 for r in results)  # noqa: E731
    n_turns = sum(len(r["turns"]) for r in results)
    return {
        "conversations_run": len(results),
        "passed": sum(r["outcome"] == "pass" for r in results),
        "failed": sum(r["outcome"] == "fail" for r in results),
        "provider_errors": sum(r["outcome"] == "provider_error" for r in results),
        "turns": n_turns,
        "turn_latency_ms": {
            "p50": percentile(latencies, 50),
            "p95": percentile(latencies, 95),
            "max": max(latencies) if latencies else None,
            "mean": round(statistics.fmean(latencies), 1) if latencies else None,
        },
        "llm_calls": usage_total("llm_calls"),
        "llm_calls_per_turn": round(usage_total("llm_calls") / n_turns, 2) if n_turns else None,
        "side_channel_calls": usage_total("side_channel_calls"),
        "empty_completions": usage_total("empty_completions"),
        "failed_llm_calls": usage_total("failed_calls"),
        "prompt_tokens": usage_total("prompt_tokens"),
        "completion_tokens": usage_total("completion_tokens"),
        "reasoning_tokens": usage_total("reasoning_tokens"),
        "cached_prompt_tokens": usage_total("cached_prompt_tokens"),
        "request_thought_signatures": usage_total("request_thought_signatures"),
        "request_placeholder_signatures": usage_total("request_placeholder_signatures"),
        "filler_messages": sum(len(r["metrics"]["filler_messages"]) for r in results),
        "bot_text_metrics": {
            name: sum(len(r["metrics"].get(name, [])) for r in results)
            for name in (spec.get("bot_text_metrics") or {})
        },
        "tool_result_metrics": {
            name: {
                "attempts": sum((r["metrics"].get(name) or {}).get("attempts", 0) for r in results),
                "total": sum((r["metrics"].get(name) or {}).get("total", 0) for r in results),
            }
            for name in (spec.get("tool_result_metrics") or {})
        },
        "log_events": {
            name: sum(r["log_events"].get(name, 0) for r in results) for name in spec.get("log_events", [])
        },
        "cost_complete": all(r["usage"]["cost_complete"] for r in results),
        **({"voice": v} if (v := aggregate_voice(results)) else {}),
    }


class ProjectVariant:
    """Apply a spec variant's text edits to project files for one run, then restore.

    `spec["variants"][name] = {"description": ..., "edits": [{"file": ...,
    "find": ..., "replace": ...}]}`. Each `find` must occur exactly once, so a
    variant cannot silently miss its target. The originals are restored in a
    finally block, so the committed project always holds the default.
    """

    def __init__(self, project: Path, spec: dict, name: Optional[str]) -> None:
        self.project = project
        self.name = name
        self.variant = (spec.get("variants") or {}).get(name) if name else None
        if name and self.variant is None:
            raise ValueError(f"unknown variant {name!r}")
        self.originals: dict[Path, str] = {}

    def __enter__(self) -> Optional[dict]:
        if not self.variant:
            return None
        for edit in self.variant["edits"]:
            path = self.project / edit["file"]
            self.originals.setdefault(path, path.read_text(encoding="utf-8"))
            current = path.read_text(encoding="utf-8")
            if current.count(edit["find"]) != 1:
                self.__exit__()
                raise ValueError(f"variant {self.name}: {edit['find']!r} must occur once in {edit['file']}")
            path.write_text(current.replace(edit["find"], edit["replace"]), encoding="utf-8")
        return {"name": self.name, **self.variant}

    def __exit__(self, *exc: Any) -> None:
        for path, text in self.originals.items():
            path.write_text(text, encoding="utf-8")
        self.originals = {}


def run_spec(project: Path, *, only: Optional[list[str]] = None, budget_usd: float,
             train: bool = True, out_root: Optional[Path] = None, label: Optional[str] = None,
             voice_mode: Optional[str] = None, variant: Optional[str] = None) -> dict:
    project = project.resolve()
    spec = load_spec(project)
    conversations = [c for c in spec["conversations"] if not only or c["id"] in only]
    started = datetime.now(timezone.utc)
    run_tag = started.strftime("%Y%m%dT%H%M%S")
    out_dir = (out_root or project / SPEC_DIR / "results") / (label or run_tag)
    raw_dir = project / SPEC_DIR / "results" / "raw" / run_tag
    out_dir.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)

    spent_before = ledger_total(project)
    server = AgentServer(project, raw_dir, price_model=spec.get("price_model"))
    results: list[dict] = []
    skipped: list[dict] = []
    driver_cls = DRIVERS[spec.get("driver", "rest")]
    # SIGTERM (kill, CI cancel) must still reach the finally block, so spend
    # already billed is always written to the ledger.
    previous_handler = signal.signal(signal.SIGTERM, _raise_exit)
    completed = False
    project_variant = ProjectVariant(project, spec, variant)
    variant_info = None
    try:
        variant_info = project_variant.__enter__()
        if variant_info and not train:
            raise ValueError("a variant changes the project, so it needs a fresh train")
        train_seconds = server.train() if train else None
        with server:
            driver = driver_cls(server.base_url, spec=spec, project=project, mode=voice_mode)
            for conv in conversations:
                recent = [r["outcome"] for r in results[-2:]]
                if len(recent) == 2 and set(recent) == {"provider_error"}:
                    # Two conversations in a row lost to the provider (quota,
                    # outage): the rest would only record the same refusal.
                    skipped.append({"id": conv["id"], "reason": "provider errors in the previous two conversations"})
                    continue
                # Speech is billed per conversation (audio streamed, characters
                # spoken), so the projection adds it to the model spend.
                run_spent = usage_log_cost(server.usage_log) + run_speech_cost(results)
                done_turns = sum(len(r["turns"]) for r in results)
                per_turn = run_spent / done_turns if done_turns else spec.get("prior_cost_per_turn_usd", 0)
                projected = spent_before + run_spent + per_turn * len(conv["turns"]) * 1.5
                if projected > budget_usd:
                    skipped.append({"id": conv["id"], "reason": f"budget: projected {projected:.4f} > {budget_usd}"})
                    continue
                print(f"… {conv['id']} ({len(conv['turns'])} turns)", flush=True)
                result = run_conversation(server, driver, spec, conv, run_tag, out_dir)
                mark = "PASS" if result["passed"] else "FAIL"
                print(f"{mark} {conv['id']}  cost={result['usage']['cost_usd']}  "
                      f"latency={[t['latency_ms'] for t in result['turns']]}", flush=True)
                results.append(result)
        completed = True
    finally:
        signal.signal(signal.SIGTERM, previous_handler)
        server.stop()
        project_variant.__exit__()
        llm_cost = usage_log_cost(server.usage_log)
        speech = run_speech_cost(results)
        ledger_append(project, {
            "run": run_tag,
            "label": label if completed else f"{label or run_tag} (interrupted)",
            "conversations": len(results),
            "cost_usd": round(llm_cost + speech, 6),
            **({"by_vendor": {"llm": llm_cost, "speech": speech}} if speech else {}),
            "finished_at": datetime.now(timezone.utc).isoformat(),
        })

    finished = datetime.now(timezone.utc)
    shutil.copy(server.usage_log, out_dir / "usage.jsonl")
    rows = read_jsonl(server.usage_log)
    pricing = next((r for r in rows if r.get("kind") == "pricing"), None)
    unattributed = [r for r in rows if r.get("kind") == "llm_call" and not r.get("sender_id")]
    report = {
        "schema": 1,
        "build": spec["build"],
        "case": spec["case"],
        "project": project.relative_to(REPO_ROOT).as_posix(),
        "model": spec.get("model"),
        "response_models": sorted({r.get("response_model") for r in rows if r.get("response_model")}),
        "channel": driver_cls.channel,
        "started_at": started.isoformat(),
        "finished_at": finished.isoformat(),
        "model_file": getattr(server, "model_file", None),
        **({"variant": variant_info} if variant_info else {}),
        "train_seconds": round(train_seconds, 1) if train_seconds else None,
        "pricing": pricing,
        "summary": {
            **aggregate(results, spec),
            "skipped": skipped,
            "cost_usd": round(usage_log_cost(server.usage_log) + run_speech_cost(results), 6),
            "llm_cost_usd": usage_log_cost(server.usage_log),
            "speech_cost_usd": run_speech_cost(results),
            "unattributed_llm_calls": len(unattributed),
            "spent_before_usd": spent_before,
            "budget_usd": budget_usd,
        },
        "conversations": results,
    }
    (out_dir / "results.json").write_text(json.dumps(report, indent=1) + "\n")
    (out_dir / "summary.md").write_text(render_summary(report, spec))
    report["out_dir"] = str(out_dir)
    return report


def render_voice_summary(v: Optional[dict], spec: dict) -> list[str]:
    if not v:
        return []
    fmt = lambda d: f"p50 {d['p50']}, p95 {d['p95']}, max {d['max']} (n={d['n']})"  # noqa: E731
    em = v["end_marker_first_message"]
    bd = v["latency_breakdown_first"]
    pricing = spec.get("speech_pricing") or {}
    lines = [
        "",
        "## Voice",
        "",
        f"- Turns: {v['turns']} ({v['audio_turns']} spoken); ended by "
        + ", ".join(f"{k} {n}" for k, n in v["turns_ended_by"].items() if n),
        f"- End of caller speech to first bot audio with sound, ms: {fmt(v['eos_to_first_audible_ms'])}",
        f"- End of caller speech to first bot marker, ms: {fmt(v['eos_to_first_marker_ms'])}",
        f"- First end marker per turn, ms: rasa_processing {fmt(em['rasa_processing_latency_ms'])}; "
        f"tts_first_byte {fmt(em['tts_first_byte_latency_ms'])}; tts_complete {fmt(em['tts_complete_latency_ms'])}",
        f"- Mantle latency_breakdown ({bd['turns_with_breakdown']} turns): "
        + "; ".join(f"{k} {fmt(d)}" for k, d in bd.items() if isinstance(d, dict) and d["n"]),
        f"- Speech-to-text: {v['asr']['turns_checked']} spoken turns, WER mean {v['asr']['wer_mean']}, "
        f"{v['asr']['turns_heard_nothing']} heard nothing, {v['asr']['turns_split']} split into more than one user event",
        "- Checked tokens: " + "; ".join(
            f"{kind} {t['exact']}/{t['checked']} exact, {t['normalised']}/{t['checked']} after number normalisation"
            for kind, t in v["asr"]["tokens"].items()),
        f"- Speech usage: {v['stt_audio_seconds']} s streamed to speech-to-text, {v['tts_characters']} characters "
        f"of bot text (upper bound for text-to-speech); {v['stt_usd']} + {v['tts_usd']} = {v['speech_cost_usd']} USD"
        + ("" if v["speech_cost_complete"] else " (incomplete: a speech price is unverified)"),
    ]
    for part in ("stt", "tts"):
        price = pricing.get(part) or {}
        if price:
            lines.append(f"- {part.upper()} price: {price.get('vendor')} {price.get('model')}, "
                         f"{price.get('usd_per_minute') or price.get('usd_per_1k_characters')} USD per "
                         f"{'minute' if 'usd_per_minute' in price else '1,000 characters'}, from {price.get('source')} "
                         f"on {price.get('checked')}")
    return lines


OUTCOME_LABELS = {"pass": "pass", "fail": "FAIL", "provider_error": "ERROR (provider)"}


def rerender(results_path: Path) -> dict:
    """Recompute outcomes and summary.md for a stored run, with no model calls."""
    report = json.loads(results_path.read_text())
    project = REPO_ROOT / report["project"]
    spec = load_spec(project)
    convs = {c["id"]: c for c in spec["conversations"]}
    usage_rows = read_jsonl(results_path.parent / "usage.jsonl")
    for r in report["conversations"]:
        if usage_rows:
            # Calls that landed after the run attributed usage (for example a
            # model turn after a voice hangup) are in the stored log; recount.
            r["usage"] = usage_for(usage_rows, r["conversation_id"])
        r["outcome"] = classify(r.get("error"), r["checks"], r["usage"])
        tracker_file = results_path.parent / "trackers" / f"{r['id']}.json"
        if r.get("voice") and r["id"] in convs and tracker_file.is_file():
            # Speech-to-text checks and speech cost are derived data: recompute
            # them from the stored turns, tracker and call stats.
            r["voice"] = voice_report(spec, convs[r["id"]], r["turns"], json.loads(tracker_file.read_text()),
                                      r["voice"].get("call"))
    report["summary"].update(aggregate(report["conversations"], spec))
    results_path.write_text(json.dumps(report, indent=1) + "\n")
    (results_path.parent / "summary.md").write_text(render_summary(report, spec))
    return report


def render_summary(report: dict, spec: dict) -> str:
    s = report["summary"]
    lat = s["turn_latency_ms"]
    lines = [
        f"# {report['build']}: run summary",
        "",
        f"- Case: `{report['case']}`; channel: {report['channel']}; model: `{report['model']}` "
        f"(provider reported {', '.join(report['response_models']) or 'n/a'})",
        f"- Run: {report['started_at'][:19]}Z to {report['finished_at'][:19]}Z",
        *([f"- Variant `{report['variant']['name']}`: {report['variant'].get('description', '')}"]
          if report.get("variant") else []),
        f"- Conversations: {s['conversations_run']} run, {s['passed']} passed, {s['failed']} failed"
        + (f", {s['provider_errors']} lost to provider errors" if s.get("provider_errors") else "")
        + (f", {len(s['skipped'])} skipped for budget" if s["skipped"] else ""),
        f"- Caller turns: {s['turns']}; turn latency p50 {lat['p50']} ms, p95 {lat['p95']} ms, "
        f"max {lat['max']} ms",
        f"- LLM calls: {s['llm_calls']} ({s['llm_calls_per_turn']} per caller turn, "
        f"{s['side_channel_calls']} side-channel, {s['empty_completions']} empty completions)",
        f"- Tokens: {s['prompt_tokens']} prompt ({s['cached_prompt_tokens']} cached), "
        f"{s['completion_tokens']} completion (of which {s['reasoning_tokens']} reasoning)",
        f"- Thought signatures sent back: {s['request_thought_signatures']} "
        f"({s['request_placeholder_signatures']} LiteLLM placeholders)",
        f"- Bot text sent as 'filler' alongside a tool call: {s['filler_messages']}; "
        + "; ".join(f"{k}: {v}" for k, v in s["bot_text_metrics"].items()),
        *[f"- Case metric {k}: {m['total']} over {m['attempts']} tool results"
          for k, m in (s.get("tool_result_metrics") or {}).items()],
        f"- Server log events: " + (", ".join(f"{k} {v}" for k, v in s["log_events"].items()) or "none"),
        f"- Cost: {s['cost_usd']} USD"
        + (f" ({s['llm_cost_usd']} model, {s['speech_cost_usd']} speech)" if s.get("speech_cost_usd") else "")
        + ("" if s["cost_complete"] else " (incomplete: some calls had no LiteLLM price)")
        + f"; model calls priced by LiteLLM {((report.get('pricing') or {}).get('litellm_version'))} bundled map",
        *render_voice_summary(s.get("voice"), spec),
        "",
        "| Conversation | Kind | Result | Domain tool calls | Turn latency ms | Cost USD |",
        "|---|---|---|---|---|---|",
    ]
    for r in report["conversations"]:
        tools = ", ".join(
            f"{c['tool']}→{c['result_status']}" + (f"/{c['result_reason']}" if c["result_reason"] else "")
            for c in r["tool_calls"] if c["source"] == "llm" or c["tool"] not in ("load_caller_profile",)
        ) or "none"
        lines.append(
            f"| {r['id']} | {r.get('kind') or ''} | {OUTCOME_LABELS[r['outcome']]} | {tools} | "
            f"{', '.join('n/a' if t['latency_ms'] is None else str(round(t['latency_ms'])) for t in r['turns'])} "
            f"| {r['usage']['cost_usd']} |"
        )
    failures = [r for r in report["conversations"] if r["outcome"] == "fail"]
    errors = [r for r in report["conversations"] if r["outcome"] == "provider_error"]
    if errors:
        lines += ["", "## Provider errors", ""]
        for r in errors:
            lines.append(
                f"- `{r['id']}`: {r['usage']['failed_calls']} failed model call(s); "
                "not evidence about the agent. See usage.jsonl for the provider message."
            )
    if failures:
        lines += ["", "## Failed checks", ""]
        for r in failures:
            for c in r["checks"]:
                if not c["passed"]:
                    lines.append(f"- `{r['id']}`: {json.dumps(c['check'])} ({c['detail']})")
            if r["error"]:
                lines.append(f"- `{r['id']}`: driver error {r['error']}")
    lines += ["", spec.get("summary_note", "").strip(), ""]
    return "\n".join(lines)
