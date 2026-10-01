#!/usr/bin/env python3
"""Run the shared conversation spec against one version of the agent, over browser audio.

    python3 shared/spec/run_spec.py rasa --label 2026-09-30-live --budget-usd 4
    python3 shared/spec/run_spec.py rasa --only normal-lisinopril --label estimate
    python3 shared/spec/run_spec.py langgraph --server-cmd "uv run python server.py --port {port}" ...

Stdlib only; runs under a bare ``python3``. For each conversation it places a
call on the agent's browser_audio WebSocket (``scripts/case_builds/
voice_driver.py``, the case-build harness's caller), streams the recorded
caller audio in real time, plays and acknowledges the agent's audio, and
waits for each bot turn. Then it judges the call from the clinic's audit log
(``shared/clinic``, ``CEDAR_AUDIT_LOG``) with ``checks.py``: the same checks
and the same invariants whichever framework answered.

The runner starts the agent itself, so it controls three environment
variables in the agent process: ``CEDAR_AUDIT_LOG`` (where the clinic writes
its audit log), and ``OPENAI_BASE_URL`` / ``OPENAI_API_BASE`` (pointed at
``llm_meter.py``, which times and prices every model call the same way for
all three). Keys come from the agent folder's ``.env`` or the repository
root's, loaded into the agent process only and never printed.

What each framework has to provide is in ``../web/PROTOCOL.md``: the
browser_audio WebSocket, the ``X-Rasa-Sender-Id`` conversation id, the
``latency`` fields on end markers, and a conversation-events endpoint the
runner polls to know when a bot turn has ended (Rasa: its tracker).

Results go to ``results/<framework>/<label>/``: ``results.json``,
``summary.md``, ``audit.jsonl``, ``llm-calls.jsonl`` and ``events/``. The
server log stays in ``raw/`` (not committed). ``--budget-usd`` caps this run's
spend; every run is appended to ``results/<framework>/spend-ledger.json``,
which is the record across runs, not the cap.
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import signal
import socket
import statistics
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

HERE = Path(__file__).resolve().parent
TUTORIAL = HERE.parents[1]
REPO = TUTORIAL.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "scripts" / "case_builds"))
sys.path.insert(0, str(REPO / "scripts"))

import checks  # noqa: E402
import voice_driver  # noqa: E402
from harness import agent_env, percentile  # noqa: E402
from llm_meter import LLMMeter  # noqa: E402

sys.path.insert(0, str(TUTORIAL / "shared" / "clinic"))
from cedar_clinic.audit import read_log  # noqa: E402

SPEC_FILE = HERE / "conversations.json"

#: How to start and observe each version. The LangGraph and Strands entries
#: are the defaults PROTOCOL.md asks those servers to follow; pass
#: --server-cmd to say how to start yours.
PRESETS: dict[str, dict[str, Any]] = {
    "rasa": {
        "cwd": "rasa",
        # rasa_call_purposes.py attaches the case-build harness's LiteLLM
        # usage logger (a Rasa-only cross-check on the meter's token counts)
        # and labels each model call with the Mantle function that made it
        # (call-purposes.jsonl). Neither changes a request.
        "server_cmd": "uv run --locked python ../shared/spec/rasa_call_purposes.py run --enable-api "
                      "-p {port} -i 127.0.0.1",
        "train_cmd": "uv run --locked rasa train",
        "ready_path": "/status",
        "events_path": "/conversations/{id}/tracker",
        "ws_path": "/webhooks/browser_audio/websocket",
        "session_end_turn": True,
    },
    "langgraph": {"cwd": "langgraph", "server_cmd": None, "train_cmd": None, "ready_path": "/health",
                  "events_path": "/conversations/{id}/events", "ws_path": "/webhooks/browser_audio/websocket",
                  "session_end_turn": False},
    "strands": {"cwd": "strands", "server_cmd": None, "train_cmd": None, "ready_path": "/health",
                "events_path": "/conversations/{id}/events", "ws_path": "/webhooks/browser_audio/websocket",
                "session_end_turn": False},
}


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def http_json(url: str, timeout: float = 10.0) -> Any:
    with urllib.request.urlopen(url, timeout=timeout) as response:
        body = response.read()
    return json.loads(body) if body else None


def _events(doc: Optional[dict], kind: str) -> list[dict]:
    return [e for e in (doc or {}).get("events", []) if e.get("event") == kind]


class AgentProcess:
    def __init__(self, cmd: str, cwd: Path, env: dict, log: Path) -> None:
        self.cmd, self.cwd, self.env, self.log = cmd, cwd, env, log
        self.proc: Optional[subprocess.Popen] = None

    def start(self, ready_url: str, timeout: float) -> float:
        began = time.monotonic()
        self.log.parent.mkdir(parents=True, exist_ok=True)
        handle = open(self.log, "w", encoding="utf-8")
        self.proc = subprocess.Popen(shlex.split(self.cmd), cwd=self.cwd, env=self.env, stdout=handle,
                                     stderr=subprocess.STDOUT, start_new_session=True)
        while time.monotonic() - began < timeout:
            if self.proc.poll() is not None:
                raise RuntimeError(f"agent exited during startup; see {self.log}")
            try:
                with urllib.request.urlopen(ready_url, timeout=3) as response:
                    if response.status == 200:
                        return time.monotonic() - began
            except (urllib.error.URLError, OSError):
                pass
            time.sleep(1.0)
        self.stop()
        raise RuntimeError(f"agent not ready after {timeout}s; see {self.log}")

    def stop(self) -> None:
        if self.proc and self.proc.poll() is None:
            os.killpg(self.proc.pid, signal.SIGINT)
            try:
                self.proc.wait(timeout=20)
            except subprocess.TimeoutExpired:
                os.killpg(self.proc.pid, signal.SIGKILL)
        self.proc = None


# ----------------------------------------------------------------------------
# One call
# ----------------------------------------------------------------------------


def speech_cost(spec: dict, stt_seconds: float) -> float:
    """Speech-to-text spend from the spec's price row (or ``--speech-prices``)."""
    rate = ((spec.get("speech_prices") or {}).get("stt") or {}).get("usd_per_hour")
    return round(stt_seconds / 3600 * rate, 6) if rate else 0.0


def tts_cost(spec: dict, characters: int) -> float:
    """Text-to-speech spend, when the price row has one. Speechmatics' preview TTS has none (0)."""
    rate = ((spec.get("speech_prices") or {}).get("tts") or {}).get("usd_per_1k_characters")
    return round(characters / 1000 * rate, 6) if rate else 0.0


def budget_check(run_cost: float, calls_done: int, prior_per_call: float, budget_usd: float) -> Optional[str]:
    """Why the next call would cross this run's cap, or None if it may run.

    The cap is per run: ``run_cost`` is what this run has spent so far. The
    framework's ledger is the record across runs and does not count against it,
    so a reader's fresh run is not blocked by the spend recorded here.
    """
    per_call = (run_cost / calls_done) if calls_done else prior_per_call
    if run_cost + 1.5 * per_call > budget_usd:
        return f"budget: {run_cost:.3f} spent in this run, next call projected {1.5 * per_call:.3f}, cap {budget_usd}"
    return None


def wait_after_call(fetch, conversation_id: str, session_end_turn: bool, timeout: float = 30.0) -> Optional[float]:
    """Let the agent finish work that follows the hangup, so its calls stay with this conversation.

    Rasa runs one more model turn on /session_end; for it, wait for that
    turn's bot_turn_ended. Otherwise wait until the events stop changing for 2 s.
    """
    began = time.monotonic()
    last, stable_since = None, time.monotonic()
    while time.monotonic() - began < timeout:
        try:
            doc = fetch(conversation_id)
        except Exception:
            doc = None
        events = (doc or {}).get("events", [])
        if session_end_turn:
            ends = [i for i, e in enumerate(events) if e.get("event") == "user" and e.get("text") == "/session_end"]
            if ends and any(e.get("event") == "bot_turn_ended" for e in events[ends[-1]:]):
                return round(time.monotonic() - began, 2)
        else:
            if len(events) != last:
                last, stable_since = len(events), time.monotonic()
            elif time.monotonic() - stable_since >= 2.0:
                return round(time.monotonic() - began, 2)
        time.sleep(0.5)
    return None


def turn_latency(turn: dict, user_events: list[dict], meter_rows: list[dict], window_end: float) -> dict:
    """The per-turn latency parts, all measured the same way for every framework."""
    v = turn["voice"]
    eos = v.get("speech_off_epoch")
    audible = eos + turn["latency_ms"] / 1000 if eos is not None and turn.get("latency_ms") is not None else None
    heard_at = checks.first(e.get("timestamp") for e in user_events if e.get("timestamp"))
    markers = voice_driver.dedupe_latency_markers(v.get("end_markers") or [])
    first_marker = markers[0] if markers else {}
    before_audio = [r for r in meter_rows if audible is not None and r["ts_start"] < audible]
    return {
        "eos_to_first_audible_ms": turn.get("latency_ms"),
        "eos_to_first_marker_ms": v.get("eos_to_first_marker_ms"),
        "eos_to_transcript_ms": round((heard_at - eos) * 1000, 1) if heard_at and eos else None,
        "agent_processing_ms": first_marker.get("rasa_processing_latency_ms"),
        "tts_first_byte_ms": first_marker.get("tts_first_byte_latency_ms"),
        "llm_calls": len(meter_rows),
        "llm_ms_total": round(sum(r.get("duration_ms") or 0 for r in meter_rows), 1),
        "llm_calls_before_first_audio": len(before_audio),
        "llm_ms_before_first_audio": round(sum(r.get("duration_ms") or 0 for r in before_audio), 1),
        "llm_ttfb_first_call_ms": before_audio[0].get("ttfb_ms") if before_audio else None,
    }


def run_conversation(args, spec: dict, conv: dict, framework: str, run_tag: str, ws_url: str, fetch,
                     meter: LLMMeter, audit_path: Path, out_dir: Path, session_end_turn: bool) -> dict:
    voice = spec["voice"]
    conversation_id = f"{framework}-{conv['id']}-{run_tag}"
    audio_dir = HERE / voice["caller_audio_dir"]
    started = time.time()
    turn_starts: list[float] = []
    turns: list[dict] = []
    error = None
    greeting: dict = {}
    call_stats: dict = {}
    call = voice_driver.BrowserAudioCall(ws_url, conversation_id, sender_header=voice["sender_header"],
                                         fetch_tracker=fetch, turn_timeout_s=float(voice["turn_timeout_s"]))
    try:
        greeting = call.open()
        for turn in conv["turns"]:
            turn_starts.append(time.time())
            if args.mode == "text":
                result = call.say(text=turn["user"], think_s=voice["think_s"])
            else:
                name = voice_driver.turn_audio_name(turn, voice["default_caller_voice"])
                pcm, rate = voice_driver.load_pcm16(audio_dir / name)
                if rate != call.rate:
                    raise ValueError(f"{name} is {rate} Hz; the handshake asked for {call.rate} Hz")
                result = call.say(pcm=pcm, think_s=voice["think_s"])
            result.pop("bot_pcm", None)
            turns.append({"user": turn["user"], **result})
            if result["voice"]["ended_by"] in ("timeout", "closed") and not result["bot_messages"]:
                raise RuntimeError(f"no bot turn after caller turn ({result['voice']['ended_by']})")
    except Exception as exc:  # recorded, never hidden
        error = f"{type(exc).__name__}: {exc}"
    finally:
        try:
            call_stats = call.close() if getattr(call, "ws", None) is not None else {}
        except Exception as exc:
            error = error or f"{type(exc).__name__} on close: {exc}"
    call_stats["after_call_wait_s"] = wait_after_call(fetch, conversation_id, session_end_turn)
    ended = time.time()

    try:
        events_doc = fetch(conversation_id) or {}
    except Exception as exc:
        events_doc = {"error": str(exc)}
    (out_dir / "events").mkdir(parents=True, exist_ok=True)
    (out_dir / "events" / f"{conv['id']}.json").write_text(json.dumps(events_doc, indent=1, default=str) + "\n")

    entries = read_log(audit_path, conversation_id)
    calls = checks.calls_from_audit(entries, turn_starts)
    check_results = checks.run_checks(conv["checks"], calls)
    invariants = {
        "guard_held": checks.guard_violations(calls),
        "no_tool_errors": [c["tool"] for c in calls if c["is_error"]],
    }
    bot_texts = [e.get("text") or "" for e in _events(events_doc, "bot")]
    user_events = _events(events_doc, "user")
    rows = meter.rows_between(started, ended + 0.001)
    llm_errors = [r for r in rows if (r.get("status") or 0) >= 400]

    latencies = []
    for i, turn in enumerate(turns):
        lo = turn_starts[i]
        hi = turn_starts[i + 1] if i + 1 < len(turn_starts) else ended
        in_turn_users = [e for e in user_events if lo <= float(e.get("timestamp") or 0) < hi]
        latencies.append(turn_latency(turn, in_turn_users, [r for r in rows if lo <= r["ts_start"] < hi], hi))

    passed_checks = all(c["passed"] for c in check_results)
    guard_ok = not invariants["guard_held"]
    if llm_errors:
        outcome = "provider_error"
    elif error is None and passed_checks and guard_ok and not invariants["no_tool_errors"]:
        outcome = "pass"
    else:
        outcome = "fail"
    stt_seconds = float(call_stats.get("audio_seconds_sent") or 0)
    tts_characters = sum(len(t) for t in bot_texts)
    usage = {
        "stt_audio_seconds": round(stt_seconds, 2),
        "tts_characters": tts_characters,
        "stt_cost_usd": speech_cost(spec, stt_seconds),
        "tts_cost_usd": tts_cost(spec, tts_characters),
        "llm_calls": len(rows),
        "failed_calls": len(llm_errors),
        "error_codes": sorted({str(r.get("error_code")) for r in llm_errors}),
        "prompt_tokens": sum((r.get("usage") or {}).get("prompt_tokens") or 0 for r in rows),
        "cached_tokens": sum((r.get("usage") or {}).get("cached_tokens") or 0 for r in rows),
        "completion_tokens": sum((r.get("usage") or {}).get("completion_tokens") or 0 for r in rows),
        "reasoning_tokens": sum((r.get("usage") or {}).get("reasoning_tokens") or 0 for r in rows),
        "llm_cost_usd": round(sum(r.get("cost_usd") or 0 for r in rows), 6),
        "cost_complete": all(r.get("cost_usd") is not None for r in rows if (r.get("status") or 0) < 400),
    }
    usage["cost_usd"] = round(usage["llm_cost_usd"] + usage["stt_cost_usd"] + usage["tts_cost_usd"], 6)
    asr = []
    for spec_turn, observed in zip(conv["turns"], turns):
        if observed["voice"].get("mode") != "audio":
            continue
        heard = " ".join(h for h in observed["voice"].get("heard") or [] if h)
        asr.append({"intended": spec_turn["user"], "heard": observed["voice"].get("heard"),
                    "wer": voice_driver.word_error_rate(spec_turn["user"], heard),
                    "tokens": voice_driver.check_tokens(heard, spec_turn.get("asr_tokens", []))})
    return {
        "id": conv["id"],
        "kind": conv["kind"],
        "description": conv["description"],
        "conversation_id": conversation_id,
        "outcome": outcome,
        "error": error,
        "checks": check_results,
        "invariants": invariants,
        "turns": [{"user": t["user"], "heard": t["voice"].get("heard"),
                   "bot": [m.get("text") for m in t["bot_messages"] if m.get("text")],
                   "ended_by": t["voice"].get("ended_by"), "latency": lat,
                   "end_markers": voice_driver.dedupe_latency_markers(t["voice"].get("end_markers") or [])}
                  for t, lat in zip(turns, latencies)],
        "audit": checks.summarise_calls(calls),
        "metrics": {
            "approval_claim_messages": checks.approval_claim_messages(bot_texts),
            "internal_id_messages": checks.internal_ids_spoken(bot_texts),
            **{name: checks.tool_result_metric(m, calls) for name, m in spec["tool_result_metrics"].items()},
        },
        "usage": usage,
        "asr": asr,
        "call": {**call_stats, **greeting, "mode": args.mode, "seconds": round(ended - started, 1)},
    }


# ----------------------------------------------------------------------------
# Aggregation and report
# ----------------------------------------------------------------------------


def pcts(values: list) -> dict:
    values = [v for v in values if isinstance(v, (int, float))]
    return {"n": len(values), "p50": percentile(values, 50), "p95": percentile(values, 95),
            "max": round(max(values), 1) if values else None}


LATENCY_KEYS = ("eos_to_first_audible_ms", "eos_to_transcript_ms", "agent_processing_ms", "tts_first_byte_ms",
                "llm_ms_before_first_audio", "llm_calls_before_first_audio", "llm_ttfb_first_call_ms",
                "eos_to_first_marker_ms", "llm_calls", "llm_ms_total")


def aggregate(results: list[dict]) -> dict:
    kinds = sorted({r["kind"] for r in results})
    turns = [t for r in results for t in r["turns"]]
    asr = [a for r in results for a in r["asr"]]
    wers = [a["wer"] for a in asr if a["wer"] is not None]
    tokens: dict[str, dict] = {}
    for a in asr:
        for tok in a["tokens"]:
            k = tokens.setdefault(tok["kind"], {"checked": 0, "exact": 0, "normalised": 0})
            k["checked"] += 1
            k["exact"] += tok["exact"]
            k["normalised"] += tok["normalised"]
    return {
        "conversations_run": len(results),
        "passed": sum(r["outcome"] == "pass" for r in results),
        "failed": sum(r["outcome"] == "fail" for r in results),
        "provider_errors": sum(r["outcome"] == "provider_error" for r in results),
        "by_kind": {k: {"run": sum(r["kind"] == k for r in results),
                        "passed": sum(r["kind"] == k and r["outcome"] == "pass" for r in results)} for k in kinds},
        "guard_violations": sum(len(r["invariants"]["guard_held"]) for r in results),
        "adversarial_guard_violations": sum(len(r["invariants"]["guard_held"]) for r in results
                                            if r["kind"] == "adversarial"),
        "refill_requests_with_effect": sum(r["metrics"]["refill_requests_with_effect"]["total"] for r in results),
        "prescription_records_changed": sum(r["metrics"]["prescription_records_changed"]["total"] for r in results),
        "approval_claim_messages": sum(len(r["metrics"]["approval_claim_messages"]) for r in results),
        "internal_id_messages": sum(len(r["metrics"]["internal_id_messages"]) for r in results),
        "bot_messages": sum(len(t["bot"]) for t in turns),
        "turns": len(turns),
        "turns_ended_by": {k: sum(t["ended_by"] == k for t in turns) for k in ("tracker", "quiet_window", "timeout",
                                                                              "closed")},
        "latency_ms": {k: pcts([t["latency"].get(k) for t in turns]) for k in LATENCY_KEYS},
        "asr": {"turns_checked": len(asr), "turns_split": sum(len(a["heard"] or []) > 1 for a in asr),
                "turns_heard_nothing": sum(not (a["heard"] or []) for a in asr),
                "wer_mean": round(statistics.fmean(wers), 3) if wers else None, "tokens": tokens},
        "llm_calls": sum(r["usage"]["llm_calls"] for r in results),
        "prompt_tokens": sum(r["usage"]["prompt_tokens"] for r in results),
        "cached_tokens": sum(r["usage"]["cached_tokens"] for r in results),
        "completion_tokens": sum(r["usage"]["completion_tokens"] for r in results),
        "reasoning_tokens": sum(r["usage"]["reasoning_tokens"] for r in results),
        "llm_cost_usd": round(sum(r["usage"]["llm_cost_usd"] for r in results), 6),
        "stt_audio_seconds": round(sum(r["usage"]["stt_audio_seconds"] for r in results), 1),
        "stt_cost_usd": round(sum(r["usage"]["stt_cost_usd"] for r in results), 6),
        "tts_characters": sum(r["usage"]["tts_characters"] for r in results),
        "tts_cost_usd": round(sum(r["usage"].get("tts_cost_usd") or 0 for r in results), 6),
        "cost_usd": round(sum(r["usage"]["cost_usd"] for r in results), 6),
        "cost_complete": all(r["usage"]["cost_complete"] for r in results),
    }


def fmt(v: Any) -> str:
    if v is None:
        return "n/a"
    if isinstance(v, float):
        return f"{v:,.0f}" if abs(v) >= 100 else f"{v:g}"
    return f"{v:,}" if isinstance(v, int) else str(v)


def spend_line(report: dict) -> str:
    a = report["aggregate"]
    prices = report.get("speech_prices") or {}
    stt = (prices.get("stt") or {}).get("vendor", "speechmatics").capitalize()
    tts_row = prices.get("tts") or {}
    tts = tts_row.get("vendor", "speechmatics").capitalize()
    if a.get("tts_cost_usd"):
        tts_part = (f" + {tts} text-to-speech {a['tts_cost_usd']:.4f} ({a['tts_characters']:,} characters of bot "
                    f"text at {tts_row['usd_per_1k_characters']} USD per 1,000)")
    else:
        tts_part = (f"; {tts} text-to-speech {a['tts_characters']:,} characters, unpriced (preview, no published "
                    "price)")
    return (f"- Spend: {a['cost_usd']:.4f} USD = model {a['llm_cost_usd']:.4f} + {stt} speech-to-text "
            f"{a['stt_cost_usd']:.4f} ({a['stt_audio_seconds']:,} s streamed){tts_part}")


def render_summary(report: dict) -> str:
    a = report["aggregate"]
    lines = [
        f"# {report['framework']}: shared spec, {report['label']}",
        "",
        f"- Run: {report['started_at']} to {report['ended_at']}, mode `{report['mode']}`, "
        f"{a['conversations_run']} conversations, {a['turns']} caller turns",
        f"- Model: {report['spec_model']}; model calls through `llm_meter.py`",
        f"- Passed **{a['passed']} of {a['conversations_run']}**; failed {a['failed']}; "
        f"provider errors {a['provider_errors']}",
        f"- Guard violations (audit invariant `guard_held`): {a['guard_violations']} "
        f"(adversarial calls: {a['adversarial_guard_violations']})",
        f"- Refill requests with effect: {a['refill_requests_with_effect']}; prescription records changed: "
        f"{a['prescription_records_changed']}; bot messages with approval wording: {a['approval_claim_messages']} "
        f"of {a['bot_messages']}; bot messages reading out an internal id: {a['internal_id_messages']}",
        spend_line(report),
        f"- Model calls: {a['llm_calls']} "
        f"({a['prompt_tokens']:,} input tokens, {a['cached_tokens']:,} cached, {a['completion_tokens']:,} output, "
        f"{a['reasoning_tokens']:,} of them reasoning){'' if a['cost_complete'] else ' (incomplete: some calls unpriced)'}",
        "",
        "## By kind",
        "",
        "| Kind | Run | Passed |",
        "|---|---|---|",
        *[f"| {k} | {v['run']} | {v['passed']} |" for k, v in a["by_kind"].items()],
        "",
        "## Latency per caller turn, ms",
        "",
        "| Part | n | p50 | p95 | max | How it is measured |",
        "|---|---|---|---|---|---|",
    ]
    how = {
        "eos_to_first_audible_ms": "Client: last voiced 10 ms of the caller audio to the first bot audio frame with sound",
        "eos_to_transcript_ms": "Agent's user-event timestamp minus the client's end of speech: end-of-turn silence plus transcription",
        "agent_processing_ms": "End marker `rasa_processing_latency_ms`: final transcript to first bot message ready for TTS",
        "tts_first_byte_ms": "End marker `tts_first_byte_latency_ms`: TTS start to first audio byte",
        "llm_ms_before_first_audio": "Meter: summed duration of model calls that started before the first bot audio",
        "llm_calls_before_first_audio": "Meter: model calls started before the first bot audio (count, not ms)",
        "llm_ttfb_first_call_ms": "Meter: time to first response byte of the turn's first model call",
        "eos_to_first_marker_ms": "Client: end of speech to the first playback marker",
        "llm_calls": "Meter: model calls started in the turn (count, not ms)",
        "llm_ms_total": "Meter: summed duration of all model calls in the turn",
    }
    for key in LATENCY_KEYS:
        p = a["latency_ms"][key]
        lines.append(f"| `{key}` | {p['n']} | {fmt(p['p50'])} | {fmt(p['p95'])} | {fmt(p['max'])} | {how[key]} |")
    asr = a["asr"]
    lines += [
        "",
        f"Speech-to-text: {asr['turns_checked']} audio turns, word error rate mean {fmt(asr['wer_mean'])}, "
        f"{asr['turns_split']} split into more than one user message, {asr['turns_heard_nothing']} heard nothing. "
        "Checked tokens (exact / after number normalisation): "
        + ", ".join(f"{k} {v['exact']}/{v['normalised']} of {v['checked']}" for k, v in sorted(asr["tokens"].items()))
        + ".",
        "",
        "## Conversations",
        "",
        "| Conversation | Kind | Outcome | Failed checks | Guard | Turns | Cost USD |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in report["conversations"]:
        failed = [c["detail"] + f" ({c['check'].get('type')} {c['check'].get('tool', '')})".rstrip()
                  for c in r["checks"] if not c["passed"]]
        guard = "held" if not r["invariants"]["guard_held"] else "; ".join(r["invariants"]["guard_held"])
        note = "; ".join(failed) or ("" if not r["error"] else r["error"])
        lines.append(f"| `{r['id']}` | {r['kind']} | {r['outcome']} | {note or '-'} | {guard} | {len(r['turns'])} | "
                     f"{r['usage']['cost_usd']:.4f} |")
    lines += ["", "Checks read the clinic's audit log only (`audit.jsonl`). Per-turn transcripts, heard text, "
              "latency parts and audit entries are in `results.json`.", ""]
    return "\n".join(lines)


# ----------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------


def ledger_total(path: Path) -> float:
    if not path.is_file():
        return 0.0
    return round(sum(r.get("cost_usd") or 0 for r in json.loads(path.read_text())["runs"]), 6)


def ledger_append(path: Path, entry: dict) -> None:
    data = json.loads(path.read_text()) if path.is_file() else {"runs": []}
    data["runs"].append(entry)
    data["total_cost_usd"] = round(sum(r.get("cost_usd") or 0 for r in data["runs"]), 6)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("framework", choices=sorted(PRESETS))
    parser.add_argument("--label", default=None, help="results folder name (default: timestamp)")
    parser.add_argument("--spec", default=str(SPEC_FILE),
                        help="conversation spec file (default: conversations.json, the 17 headline calls)")
    parser.add_argument("--only", nargs="*", help="conversation ids to run")
    parser.add_argument("--mode", choices=("audio", "text"), default="audio",
                        help="audio streams the caller WAVs; text sends {\"text\"} frames (skips speech-to-text)")
    parser.add_argument("--budget-usd", type=float, default=4.0,
                        help="cap on this run's spend (model + priced speech); the ledger records every run")
    parser.add_argument("--speech-prices", default=None,
                        help="JSON file replacing the spec's speech_prices (another speech vendor's price rows)")
    parser.add_argument("--server-cmd", default=None, help="command that starts the agent; {port} is substituted")
    parser.add_argument("--server-cwd", default=None, help="folder to start it in (default: the framework folder)")
    parser.add_argument("--no-train", action="store_true", help="skip the preset's train command")
    parser.add_argument("--base-url", default=None,
                        help="use an agent that is already running here instead of starting one (then the "
                             "agent must already have CEDAR_AUDIT_LOG and the meter env set; see --print-env)")
    parser.add_argument("--audit-log", default=None, help="with --base-url: the agent's CEDAR_AUDIT_LOG file")
    parser.add_argument("--ready-timeout", type=float, default=300.0)
    args = parser.parse_args()

    preset = PRESETS[args.framework]
    spec = json.loads(Path(args.spec).read_text())
    if args.speech_prices:
        spec["speech_prices"] = json.loads(Path(args.speech_prices).read_text())["speech_prices"]
    convs = [c for c in spec["conversations"] if not args.only or c["id"] in args.only]
    if args.only and len(convs) != len(args.only):
        parser.error(f"unknown conversation id in {args.only}")
    run_tag = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    label = args.label or run_tag
    fw_dir = TUTORIAL / "results" / args.framework
    out_dir = fw_dir / label
    raw_dir = out_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    ledger = fw_dir / "spend-ledger.json"
    audit_path = Path(args.audit_log) if args.audit_log else out_dir / "audit.jsonl"
    if audit_path.exists() and not args.audit_log:
        audit_path.unlink()
    meter = LLMMeter(spec["prices"], log_path=out_dir / "llm-calls.jsonl").start()
    (out_dir / "llm-calls.jsonl").unlink(missing_ok=True)
    (out_dir / "call-purposes.jsonl").unlink(missing_ok=True)

    agent: Optional[AgentProcess] = None
    startup_s = None
    cwd = (TUTORIAL / (args.server_cwd or preset["cwd"])).resolve()
    if args.base_url:
        base_url = args.base_url.rstrip("/")
    else:
        cmd = args.server_cmd or preset["server_cmd"]
        if not cmd:
            parser.error(f"--server-cmd is required for {args.framework}")
        port = free_port()
        base_url = f"http://127.0.0.1:{port}"
        env = agent_env(cwd, {
            "CEDAR_AUDIT_LOG": str(audit_path),
            "RASA_TELEMETRY_ENABLED": "false",
            "HF_HUB_OFFLINE": "1",
            "CASE_BUILD_USAGE_LOG": str(raw_dir / "litellm-usage.jsonl"),
            "RASA_CALL_PURPOSES_LOG": str(out_dir / "call-purposes.jsonl"),
            "LITELLM_LOCAL_MODEL_COST_MAP": "True",
            **meter.env(),
        })
        if preset.get("train_cmd") and not args.no_train:
            print(f"training: {preset['train_cmd']}", flush=True)
            with open(raw_dir / "train.log", "w", encoding="utf-8") as log:
                subprocess.run(shlex.split(preset["train_cmd"]), cwd=cwd, env=env, check=True, stdout=log,
                               stderr=subprocess.STDOUT)
        agent = AgentProcess(cmd.format(port=port), cwd, env, raw_dir / "server.log")
        print(f"starting {args.framework}: {agent.cmd}", flush=True)
        startup_s = round(agent.start(f"{base_url}{preset['ready_path']}", args.ready_timeout), 1)
        print(f"ready in {startup_s}s at {base_url}", flush=True)

    ws_url = base_url.replace("http://", "ws://", 1) + preset["ws_path"]

    def fetch(conversation_id: str) -> dict:
        return http_json(base_url + preset["events_path"].format(id=conversation_id), timeout=10)

    started_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    results: list[dict] = []
    skipped: list[dict] = []
    stop_reason = None
    consecutive_provider_errors = 0

    def stop(signum, _frame):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, stop)
    try:
        for conv in convs:
            run_cost = meter.total_cost() + sum(r["usage"]["stt_cost_usd"] + r["usage"]["tts_cost_usd"]
                                                for r in results)
            over = budget_check(run_cost, len(results), spec["prior_cost_per_call_usd"], args.budget_usd)
            if over:
                skipped.append({"id": conv["id"], "reason": over})
                continue
            if stop_reason:
                skipped.append({"id": conv["id"], "reason": stop_reason})
                continue
            print(f"→ {conv['id']}", flush=True)
            result = run_conversation(args, spec, conv, args.framework, run_tag, ws_url, fetch, meter, audit_path,
                                      out_dir, preset["session_end_turn"])
            results.append(result)
            print(f"  {result['outcome']}  cost {result['usage']['cost_usd']:.4f}  "
                  f"guard {'held' if not result['invariants']['guard_held'] else 'VIOLATED'}"
                  f"{'  ' + result['error'] if result['error'] else ''}", flush=True)
            if "insufficient_quota" in result["usage"]["error_codes"]:
                stop_reason = "OpenAI returned insufficient_quota; run stopped"
            consecutive_provider_errors = consecutive_provider_errors + 1 \
                if result["outcome"] == "provider_error" else 0
            if consecutive_provider_errors >= 2:
                stop_reason = stop_reason or "two provider-error conversations in a row; run stopped"
    except KeyboardInterrupt:
        stop_reason = "interrupted"
    finally:
        if agent is not None:
            agent.stop()
        meter.stop()

    report = {
        "framework": args.framework,
        "label": label,
        "run_tag": run_tag,
        "mode": args.mode,
        "spec": spec["spec"],
        "started_at": started_at,
        "ended_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "spec_model": spec["model"],
        "prices": spec["prices"],
        "speech_prices": spec.get("speech_prices"),
        "budget_usd": args.budget_usd,
        "agent_startup_s": startup_s,
        "server_cmd": agent.cmd if agent else None,
        "stop_reason": stop_reason,
        "skipped": skipped,
        "aggregate": aggregate(results),
        "conversations": results,
        "meter_unattributed_cost_usd": round(meter.total_cost() - sum(r["usage"]["llm_cost_usd"] for r in results), 6),
        "meter_total_cost_usd": meter.total_cost(),
    }
    (out_dir / "results.json").write_text(json.dumps(report, indent=1, default=str) + "\n")
    (out_dir / "summary.md").write_text(render_summary(report))
    stt_cost = round(sum(r["usage"]["stt_cost_usd"] for r in results), 6)
    tts_spend = round(sum(r["usage"]["tts_cost_usd"] for r in results), 6)
    entry = {"label": label, "run_tag": run_tag, "mode": args.mode, "spec": spec["spec"],
             "conversations": len(results), "cost_usd": round(meter.total_cost() + stt_cost + tts_spend, 6),
             "llm_cost_usd": meter.total_cost(), "stt_cost_usd": stt_cost,
             "source": "llm_meter.py token usage x spec prices; speech-to-text seconds x spec price"}
    if tts_spend:
        entry["tts_cost_usd"] = tts_spend
        entry["source"] += "; text-to-speech characters x price"
    if args.speech_prices:
        entry["speech_prices"] = Path(args.speech_prices).name
    ledger_append(ledger, entry)
    a = report["aggregate"]
    print(f"\n{args.framework}: passed {a['passed']}/{a['conversations_run']}, guard violations "
          f"{a['guard_violations']}, spend {entry['cost_usd']:.4f} USD (ledger, all runs: {ledger_total(ledger):.4f})")
    if stop_reason:
        print(f"stopped: {stop_reason}")
    print(f"results: {out_dir}")
    return 0 if a["conversations_run"] and a["provider_errors"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
