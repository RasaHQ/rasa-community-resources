#!/usr/bin/env python3
"""Offline voice timing analysis and opt-in, bounded runtime observation.

Only allowlisted timing metadata is retained. No SDK, model, microphone or
provider is invoked by analysis. Capture runs only the command supplied by its
caller; it never chooses credentials, a provider, a model or a retry.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import json
import math
import os
from pathlib import Path
import re
import selectors
import signal
import statistics
import subprocess
import sys
import time

SCHEMA = "rasa.voice-latency-event/v1"
MAX_LINE = 65536
MAX_EVENTS = 100000
STAGES = {
    "speech.end", "asr.final", "turn.started", "turn.completed", "tool.dispatch",
    "mcp.started", "mcp.completed", "tts.requested", "tts.first_chunk",
    "audio.first_played", "runtime.first_log", "runtime.model_loading",
    "runtime.voice_ready", "runtime.worker_ready", "asr.config",
    "capture.started", "capture.worker_ready_observed", "capture.exited", "voice.session_started",
}
ID = re.compile(r"^[A-Za-z0-9_.:-]{1,100}$")
STAMP = re.compile(r"(?<!\d)(\d{4}-\d\d-\d\d)[ T](\d\d:\d\d:\d\d)(\.\d{1,6})?")
MAPPINGS = {
    "mantle.turn.started": "turn.started",
    "mantle.turn.completed": "turn.completed",
    "mantle.tool.dispatched": "tool.dispatch",
    "barge_in.nli_model.loading": "runtime.model_loading",
    "voice_channel.initialized": "runtime.voice_ready",
    "asr.engine.initialized": "asr.config",
    "processor.handle_voice_conversation.start": "voice.session_started",
}


def finite(value, name):
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
        raise ValueError(f"invalid {name}")
    return value


def validate(row):
    if not isinstance(row, dict) or row.get("schema") != SCHEMA:
        raise ValueError("unsupported timing schema")
    if row.get("event") not in STAGES:
        raise ValueError("unsupported timing event")
    for key in ("session", "turn", "clock"):
        if not isinstance(row.get(key), str) or not ID.fullmatch(row[key]):
            raise ValueError(f"invalid {key}")
    finite(row.get("at_ms"), "at_ms")
    finite(row.get("resolution_ms", 0), "resolution_ms")
    if row.get("resolution_ms", 0) > 60000:
        raise ValueError("resolution too coarse")
    # Do not propagate arbitrary JSON fields, transcripts, URLs or payloads.
    result = {k: row[k] for k in ("schema", "event", "session", "turn", "clock", "at_ms")}
    result["resolution_ms"] = row.get("resolution_ms", 0)
    for key in ("iterations", "endpointing_ms", "utterance_end_ms"):
        if key in row:
            value = finite(row[key], key)
            if type(value) is not int:
                raise ValueError(f"invalid {key}")
            result[key] = value
    if "call" in row:
        if not isinstance(row["call"], str) or not ID.fullmatch(row["call"]):
            raise ValueError("invalid call")
        result["call"] = row["call"]
    for key in ("cancelled", "failed"):
        if key in row:
            if type(row[key]) is not bool:
                raise ValueError(f"invalid {key}")
            result[key] = row[key]
    if "exit_code" in row:
        if type(row["exit_code"]) is not int or not -255 <= row["exit_code"] <= 255:
            raise ValueError("invalid exit_code")
        result["exit_code"] = row["exit_code"]
    if "termination" in row:
        if row["termination"] not in ("normal", "timeout", "interrupt", "error"):
            raise ValueError("invalid termination")
        result["termination"] = row["termination"]
    if "cleanup" in row:
        if row["cleanup"] not in ("group_gone", "permission_denied", "still_present", "not_started"):
            raise ValueError("invalid cleanup")
        result["cleanup"] = row["cleanup"]
    return result


class SDKLog:
    """Project only actual markers; a tool dispatch is not an MCP duration."""

    def __init__(self):
        self.sessions = {}
        self.turns = {}
        self.pending = {}
        self.first = False

    def parse(self, line):
        stamp = STAMP.search(line)
        if not stamp:
            return []
        date = datetime.fromisoformat(stamp[1] + "T" + stamp[2] + (stamp[3] or ""))
        # Abstract server wall-clock axis; no assumption about local UTC offset.
        relative = date - datetime(1970, 1, 1)
        at = relative.days * 86400000 + relative.seconds * 1000 + relative.microseconds / 1000
        resolution = 10 ** (3 - len(stamp[3][1:])) if stamp[3] else 1000
        match = re.search(r"\bconversation_id=([A-Za-z0-9_-]+)", line)
        key = match[1] if match else None
        if key is not None and key not in self.sessions:
            if len(self.sessions) >= 10000:
                raise ValueError("too many sessions")
            self.sessions[key] = f"session-{len(self.sessions) + 1}"
        session = self.sessions.get(key, "runtime")

        def event(stage, turn="runtime", **meta):
            return validate(dict(schema=SCHEMA, event=stage, session=session,
                                 turn=turn, clock="server.wall", at_ms=at,
                                 resolution_ms=resolution, **meta))

        rows = []
        if not self.first:
            rows.append(event("runtime.first_log"))
            self.first = True
        marker = next((m for m in MAPPINGS if re.search(re.escape(m) + r"(?:\s|$)", line)), None)
        if "Worker ready" in line:
            rows.append(event("runtime.worker_ready"))
        if marker is None:
            return rows
        stage = MAPPINGS[marker]
        if stage.startswith("turn.") or stage == "tool.dispatch":
            if key is None:
                return rows  # Cannot join anonymous observations to a turn.
            if stage == "turn.started" or key not in self.pending:
                self.turns[key] = self.turns.get(key, 0) + 1
                self.pending[key] = f"turn-{self.turns[key]}"
            turn = self.pending[key]
            meta = {}
            if stage == "turn.completed":
                count = re.search(r"\biteration_count=(\d+)\b", line)
                if count:
                    meta["iterations"] = int(count[1])
                meta["cancelled"] = bool(re.search(r"\bsource=cancelled\b", line))
                meta["failed"] = bool(re.search(r"\berror=", line)
                                      and not re.search(r"\berror=(?:None|null)(?:\s|$)", line))
            rows.append(event(stage, turn, **meta))
            if stage == "turn.completed":
                del self.pending[key]
        else:
            meta = {}
            if stage == "asr.config":
                for source, target in (("endpointing", "endpointing_ms"),
                                       ("utterance_end_ms", "utterance_end_ms")):
                    value = re.search(r"['\"]?" + source + r"['\"]?\s*:\s*(\d+)\b", line)
                    if value:
                        meta[target] = int(value[1])
            rows.append(event(stage, **meta))
        return rows


def unique_json(pairs):
    row = {}
    for key, value in pairs:
        if key in row:
            raise ValueError("duplicate JSON field")
        row[key] = value
    return row


def read_events(path, format_):
    parser = SDKLog()
    result = []
    with Path(path).open("rb") as stream:
        while True:
            line = stream.readline(MAX_LINE + 1)
            if not line:
                break
            if len(line) > MAX_LINE:
                raise ValueError("input line exceeds 64KiB")
            text = line.decode("utf-8")
            if format_ == "sdk-log":
                result.extend(parser.parse(text))
            elif text.strip():
                result.append(validate(json.loads(text, object_pairs_hook=unique_json)))
            if len(result) > MAX_EVENTS:
                raise ValueError("too many timing events")
    return result


def span(start, end):
    if start is None or end is None:
        return {"status": "missing_boundary", "ms": None}
    if start["clock"] != end["clock"]:
        return {"status": "different_clocks", "ms": None}
    value = end["at_ms"] - start["at_ms"]
    if value < 0:
        return {"status": "reversed_boundary", "ms": None}
    uncertainty = max(start["resolution_ms"], end["resolution_ms"])
    return {"status": "observed", "ms": value,
            "resolution_ms": uncertainty, "lower_ms": max(0, value - uncertainty),
            "upper_ms_exclusive": value + uncertainty if uncertainty else None}


def summary(values):
    values = sorted(x["ms"] for x in values if x["status"] == "observed")
    return {"count": len(values), "p50_ms": statistics.median(values) if values else None,
            "p95_ms": values[math.ceil(len(values) * .95) - 1] if values else None}


def analyse(events, target_ms=1500):
    groups = {}
    runtime = {}
    voice_sessions = {r["session"] for r in events if r["event"] == "voice.session_started"}
    for row in events:
        if row["turn"] == "runtime":
            runtime.setdefault(row["event"], row)
        else:
            groups.setdefault((row["session"], row["turn"]), []).append(row)
    turns = []
    for (session, turn), rows in groups.items():
        def first(stage):
            return next((r for r in rows if r["event"] == stage), None)
        def measure(a, b):
            if any(sum(r["event"] == stage for r in rows) > 1 for stage in (a, b)):
                return {"status": "ambiguous_boundaries", "ms": None}
            return span(first(a), first(b))
        completed = first("turn.completed")
        call_ids = {r["call"] for r in rows if r["event"].startswith("mcp.") and "call" in r}
        mcp = []
        for call in sorted(call_ids):
            begin = [r for r in rows if r["event"] == "mcp.started" and r.get("call") == call]
            end = [r for r in rows if r["event"] == "mcp.completed" and r.get("call") == call]
            measured = (span(begin[0] if begin else None, end[0] if end else None)
                        if len(begin) <= 1 and len(end) <= 1 else
                        {"status": "ambiguous_call_boundaries", "ms": None})
            mcp.append(dict(call=call, **measured))
        turns.append({"session": session, "turn": turn,
                      "context": "voice_session_observed" if session in voice_sessions else "unclassified",
                      "cancelled": completed.get("cancelled", False) if completed else False,
                      "failed": completed.get("failed", False) if completed else False,
                      "iterations": completed.get("iterations") if completed else None,
                      "end_of_speech_to_first_audio": measure("speech.end", "audio.first_played"),
                      "asr_final": measure("speech.end", "asr.final"),
                      "orchestration": measure("turn.started", "turn.completed"),
                      "mcp_calls": mcp,
                      "mcp_timing_status": "observations_present" if mcp else "missing_boundaries",
                      "tool_dispatches": sum(r["event"] == "tool.dispatch" for r in rows),
                      "tts_first_chunk": measure("tts.requested", "tts.first_chunk")})
    usable = [r for r in turns if not r["cancelled"] and not r["failed"]]
    return {
        "schema": "rasa.voice-latency-report/v1", "target_ms": target_ms,
        "timing_provenance": "Supplied timing observations; not authenticated audio or a qualification receipt",
        "end_of_speech_to_first_audio": summary([r["end_of_speech_to_first_audio"] for r in usable]),
        "orchestration": summary([r["orchestration"] for r in usable]),
        "voice_session_orchestration": summary([r["orchestration"] for r in usable
                                                 if r["session"] in voice_sessions]),
        "cancelled_turns": sum(r["cancelled"] for r in turns), "turns": turns,
        "failed_turns": sum(r["failed"] for r in turns),
        "cold_start": {
            "first_runtime_log_to_worker_ready": span(runtime.get("runtime.first_log"), runtime.get("runtime.worker_ready")),
            "model_loading_to_voice_initialization": span(runtime.get("runtime.model_loading"), runtime.get("runtime.voice_ready")),
            "capture_start_to_worker_line_observed": span(runtime.get("capture.started"), runtime.get("capture.worker_ready_observed")),
        },
        "asr_configurations": [r for r in events if r["event"] == "asr.config"],
        "capture_exits": [r for r in events if r["event"] == "capture.exited"],
        "limits": ["Missing boundaries are unknown, never zero.",
                   "Server wall clocks and browser clocks are not interchangeable.",
                   "Streaming phases overlap; component times must not be added.",
                   "Turn completion is not first audible output; dispatch is not an MCP duration.",
                   "SDK wall timestamps can be coarse; intervals expose their resolution.",
                   "Percentiles describe only the observed non-cancelled samples, not typical production performance."],
    }


def capture(command, output, timeout):
    if not command:
        raise ValueError("capture requires an explicit runtime command")
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    parser = SDKLog()
    started = time.monotonic()
    process = None
    reason = None
    cleanup = "not_started"
    count = 0
    # Refuse to overwrite previous observations and keep timing artifacts private.
    descriptor = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w") as out:
        def write(row):
            nonlocal count
            count += 1
            if count > MAX_EVENTS:
                raise ValueError("too many timing events")
            out.write(json.dumps(validate(row), allow_nan=False) + "\n")
            out.flush()

        def observed(stage, **meta):
            return dict(schema=SCHEMA, event=stage, session="runtime", turn="runtime",
                        clock="capture.monotonic", at_ms=(time.monotonic() - started) * 1000,
                        resolution_ms=time.get_clock_info("monotonic").resolution * 1000, **meta)

        write(observed("capture.started"))
        try:
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                       start_new_session=True)
            with selectors.DefaultSelector() as selector:
                selector.register(process.stdout, selectors.EVENT_READ)
                buffer = b""
                eof = False
                while not eof:
                    if time.monotonic() - started >= timeout:
                        reason = "timeout"
                        break
                    for key, _ in selector.select(timeout=.1):
                        chunk = os.read(key.fd, 8192)
                        if not chunk:
                            eof = True
                            break
                        # Preserve normal terminal output, but never retain it in the artifact.
                        sys.stdout.buffer.write(chunk)
                        sys.stdout.buffer.flush()
                        buffer += chunk
                        while b"\n" in buffer:
                            line, buffer = buffer.split(b"\n", 1)
                            if len(line) > MAX_LINE:
                                raise ValueError("runtime line exceeds 64KiB")
                            text = line.decode("utf-8", errors="replace")
                            for row in parser.parse(text):
                                write(row)
                            if "Worker ready" in text:
                                write(observed("capture.worker_ready_observed"))
                        if len(buffer) > MAX_LINE:
                            raise ValueError("runtime line exceeds 64KiB")
                if buffer:
                    for row in parser.parse(buffer.decode("utf-8", errors="replace")):
                        write(row)
            if reason is None:
                process.wait(timeout=max(.01, timeout - (time.monotonic() - started)))
        except KeyboardInterrupt:
            reason = "interrupt"
        except subprocess.TimeoutExpired:
            reason = "timeout"
        except (ValueError, OSError):
            reason = "error"
            raise
        finally:
            if process is not None:
                # Signal the whole owned group even if its leader already exited.
                for sig in (signal.SIGTERM, signal.SIGKILL):
                    try:
                        os.killpg(process.pid, sig)
                    except ProcessLookupError:
                        cleanup = "group_gone"
                        break
                    except PermissionError:
                        cleanup = "permission_denied"
                        break  # No alternate signal/tool or retry after a refusal.
                    deadline = time.monotonic() + 1
                    try:
                        process.wait(timeout=1)  # Reap the leader before group-liveness probes.
                    except subprocess.TimeoutExpired:
                        pass
                    while time.monotonic() < deadline:
                        process.poll()  # reap a completed leader before probing its group
                        try:
                            os.killpg(process.pid, 0)
                        except ProcessLookupError:
                            cleanup = "group_gone"
                            break
                        except PermissionError:
                            cleanup = "permission_denied"
                            break
                        time.sleep(.02)
                    if cleanup in ("group_gone", "permission_denied"):
                        break
                    cleanup = "still_present"
                try:
                    process.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    pass
                if process.stdout is not None:
                    process.stdout.close()
            meta = {"termination": reason or ("normal" if process is not None else "error"),
                    "cleanup": cleanup}
            if process is not None and process.returncode is not None:
                meta["exit_code"] = process.returncode
            write(observed("capture.exited", **meta))
    if cleanup in ("permission_denied", "still_present"):
        return 126  # Preserve partial observations without claiming successful cleanup.
    if reason in ("interrupt", "timeout"):
        return 130 if reason == "interrupt" else 124
    return process.returncode if process.returncode >= 0 else 128 - process.returncode


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    report = sub.add_parser("analyse")
    report.add_argument("input", type=Path)
    report.add_argument("--format", choices=["sdk-log", "events"], default="sdk-log")
    report.add_argument("--output", type=Path)
    report.add_argument("--target-ms", type=float, default=1500)
    run = sub.add_parser("capture")
    run.add_argument("--output", type=Path, required=True)
    run.add_argument("--timeout", type=float, default=600)
    run.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    try:
        if args.action == "capture":
            if not math.isfinite(args.timeout) or not 0 < args.timeout <= 3600:
                raise ValueError("timeout must be positive and at most 3600 seconds")
            return capture(args.command[1:] if args.command[:1] == ["--"] else args.command,
                           args.output, args.timeout)
        if not math.isfinite(args.target_ms) or args.target_ms <= 0:
            raise ValueError("target must be positive")
        result = analyse(read_events(args.input, args.format), args.target_ms)
        text = json.dumps(result, indent=2, allow_nan=False) + "\n"
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            with args.output.open("x") as out:
                out.write(text)
        else:
            sys.stdout.write(text)
        return 0
    except (ValueError, OSError, json.JSONDecodeError) as error:
        # Do not echo source rows, command arguments, response bodies or secrets.
        print(f"voice-latency: {type(error).__name__}; no completed measurement claimed", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
