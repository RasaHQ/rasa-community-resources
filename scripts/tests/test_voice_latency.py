"""Authored timing controls; these do not establish measured voice performance."""
import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "voice_latency.py"
SPEC = importlib.util.spec_from_file_location("voice_latency", SCRIPT)
v = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(v)


def event(stage, at, *, turn="turn-1", clock="browser.monotonic", **extra):
    return v.validate(dict(schema=v.SCHEMA, event=stage, session="session-1", turn=turn,
                           clock=clock, at_ms=at, resolution_ms=0, **extra))


class TimingControls(unittest.TestCase):
    def test_orchestration_and_tts_never_substitute_for_audible_output(self):
        rows = [event("turn.started", 100), event("turn.completed", 2300, iterations=2),
                event("tts.requested", 300), event("tts.first_chunk", 500)]
        report = v.analyse(rows)
        self.assertEqual(report["end_of_speech_to_first_audio"]["count"], 0)
        self.assertIsNone(report["end_of_speech_to_first_audio"]["p50_ms"])
        self.assertEqual(report["turns"][0]["orchestration"]["ms"], 2200)
        self.assertEqual(report["turns"][0]["tts_first_chunk"]["ms"], 200)

    def test_components_overlap_and_are_not_added(self):
        rows = [event("speech.end", 0), event("asr.final", 200),
                event("turn.started", 200), event("tts.requested", 900),
                event("tts.first_chunk", 1100), event("audio.first_played", 1250),
                event("turn.completed", 2200, iterations=3)]
        report = v.analyse(rows)
        self.assertEqual(report["end_of_speech_to_first_audio"]["p50_ms"], 1250)
        self.assertEqual(report["turns"][0]["iterations"], 3)
        self.assertEqual(report["orchestration"]["p50_ms"], 2000)

    def test_browser_and_server_clocks_cannot_be_subtracted(self):
        report = v.analyse([event("speech.end", 100),
                            event("asr.final", 400, clock="server.monotonic")])
        self.assertEqual(report["turns"][0]["asr_final"]["status"], "different_clocks")
        self.assertIsNone(report["turns"][0]["asr_final"]["ms"])

    def test_multiple_speech_ends_are_ambiguous_not_a_chosen_fast_result(self):
        report = v.analyse([event("speech.end", 0), event("speech.end", 1000),
                            event("audio.first_played", 1100)])
        self.assertEqual(report["turns"][0]["end_of_speech_to_first_audio"]["status"],
                         "ambiguous_boundaries")

    def test_reversed_boundaries_are_not_negative_or_zero_samples(self):
        report = v.analyse([event("speech.end", 1000), event("audio.first_played", 900)])
        self.assertEqual(report["end_of_speech_to_first_audio"]["count"], 0)
        self.assertEqual(report["turns"][0]["end_of_speech_to_first_audio"]["status"],
                         "reversed_boundary")

    def test_mcp_call_pairs_keep_missing_and_duplicate_boundaries(self):
        rows = [event("mcp.started", 10, call="one"), event("mcp.completed", 30, call="one"),
                event("mcp.started", 40, call="two"), event("mcp.started", 50, call="three"),
                event("mcp.completed", 60, call="three"), event("mcp.completed", 70, call="three")]
        calls = {x["call"]: x for x in v.analyse(rows)["turns"][0]["mcp_calls"]}
        self.assertEqual(calls["one"]["ms"], 20)
        self.assertEqual(calls["two"]["status"], "missing_boundary")
        self.assertEqual(calls["three"]["status"], "ambiguous_call_boundaries")

    def test_cancelled_turns_are_retained_but_not_successful_samples(self):
        rows = [event("turn.started", 0), event("turn.completed", 200, cancelled=True),
                event("speech.end", 0), event("audio.first_played", 200)]
        report = v.analyse(rows)
        self.assertEqual(report["cancelled_turns"], 1)
        self.assertEqual(len(report["turns"]), 1)
        self.assertEqual(report["end_of_speech_to_first_audio"]["count"], 0)

    def test_failed_turn_is_retained_without_a_success_sample(self):
        rows = [event("turn.started", 0), event("turn.completed", 250, failed=True)]
        report = v.analyse(rows)
        self.assertEqual(report["failed_turns"], 1)
        self.assertEqual(report["orchestration"]["count"], 0)
        self.assertEqual(report["turns"][0]["orchestration"]["ms"], 250)

    def test_conflicting_terminals_are_order_independent_and_never_successes(self):
        for flag in ("cancelled", "failed"):
            for reverse in (False, True):
                ends = [event("turn.completed", 200), event("turn.completed", 250, **{flag: True})]
                rows = [event("speech.end", 0), event("audio.first_played", 200)]
                rows += list(reversed(ends)) if reverse else ends
                report = v.analyse(rows)
                self.assertTrue(report["turns"][0][flag])
                self.assertEqual(report["turns"][0]["terminal_state"], "ambiguous")
                self.assertEqual(report["ambiguous_terminal_turns"], 1)
                self.assertEqual(report["end_of_speech_to_first_audio"]["count"], 0)
        # Even two apparently successful completions are not a unique terminal.
        rows = [event("speech.end", 0), event("audio.first_played", 200),
                event("turn.completed", 250), event("turn.completed", 300)]
        self.assertEqual(v.analyse(rows)["end_of_speech_to_first_audio"]["count"], 0)
        # Completion is optional for independent, valid audio-only observations.
        audio_only = v.analyse(rows[:2])
        self.assertEqual(audio_only["end_of_speech_to_first_audio"]["count"], 1)
        self.assertEqual(audio_only["turns"][0]["terminal_state"], "absent")

    def test_percentiles_disclose_their_actual_sample_count(self):
        rows = []
        for i, latency in enumerate([100, 200, 300, 400]):
            rows += [event("speech.end", 0, turn=f"turn-{i}"),
                     event("audio.first_played", latency, turn=f"turn-{i}")]
        self.assertEqual(v.analyse(rows)["end_of_speech_to_first_audio"],
                         {"count": 4, "p50_ms": 250, "p95_ms": 400})

    def test_unknown_fields_and_transcripts_are_not_retained(self):
        row = event("speech.end", 1, transcript="PRIVATE-CANARY", token="PRIVATE-KEY")
        self.assertNotIn("PRIVATE", json.dumps(row))
        for bad in [float("nan"), float("inf"), -1, True]:
            with self.assertRaises(ValueError):
                event("speech.end", bad)


class SDKControls(unittest.TestCase):
    def parse(self, lines):
        parser = v.SDKLog()
        return [row for line in lines for row in parser.parse(line)]

    def line(self, second, marker, session="a", extra=""):
        return (f"2026-01-01 12:00:{second:02d} INFO logger - [info ] {marker} "
                f"conversation_id={session} {extra}")

    def test_native_normalized_adapter_events_need_no_console_timestamp(self):
        supplied = [event("speech.end", 100), event("audio.first_played", 1400)]
        rows = self.parse([json.dumps(x) for x in supplied])
        self.assertEqual(v.analyse(rows)["end_of_speech_to_first_audio"]["p50_ms"], 1300)

    def test_prefixed_json_sdk_events_and_private_fields_are_projected(self):
        def line(second, **row):
            return f"2026-01-01 12:00:{second:02d} INFO logger - " + json.dumps(row)
        rows = self.parse([line(0, event="mantle.turn.started", conversation_id="raw-id"),
                           line(2, event="mantle.turn.completed", conversation_id="raw-id",
                                iteration_count=2, source="completed", error=None, transcript="PRIVATE"),
                           line(3, event="unrelated", conversation_id="raw-id",
                                transcript="mantle.turn.started Worker ready")])
        report = v.analyse(rows)
        self.assertEqual(report["orchestration"]["p50_ms"], 2000)
        self.assertFalse(report["turns"][0]["failed"])
        self.assertEqual(len(report["turns"]), 1)
        self.assertNotIn("runtime.worker_ready", [r["event"] for r in rows])
        self.assertNotIn("PRIVATE", json.dumps(rows))
        self.assertNotIn("raw-id", json.dumps(rows))

    def test_coloured_sdk_markers_are_recognized_without_retaining_console(self):
        rows = self.parse([self.line(0, "\x1b[32mmantle.turn.started\x1b[0m"),
                           self.line(2, "\x1b[32mmantle.turn.completed\x1b[0m", extra="iteration_count=2")])
        report = v.analyse(rows)
        self.assertEqual(report["orchestration"]["count"], 1)
        self.assertEqual(report["orchestration"]["p50_ms"], 2000)

    def test_interleaved_sessions_are_joined_separately_and_ids_not_exported(self):
        rows = self.parse([self.line(0, "mantle.turn.started", "PRIVATE-A"),
                           self.line(1, "mantle.turn.started", "PRIVATE-B"),
                           self.line(2, "mantle.turn.completed", "PRIVATE-A", "iteration_count=2"),
                           self.line(4, "mantle.turn.completed", "PRIVATE-B", "iteration_count=3")])
        report = v.analyse(rows)
        self.assertEqual([r["orchestration"]["ms"] for r in report["turns"]], [2000, 3000])
        self.assertNotIn("PRIVATE", json.dumps(rows))
        coarse = report["turns"][0]["orchestration"]
        self.assertEqual((coarse["lower_ms"], coarse["upper_ms_exclusive"]), (1000, 3000))

    def test_truncated_next_turn_does_not_reuse_previous_start(self):
        rows = self.parse([self.line(0, "mantle.turn.started"),
                           self.line(2, "mantle.turn.completed", extra="iteration_count=2"),
                           self.line(10, "mantle.tool.dispatched", extra="tool_name=finish"),
                           self.line(11, "mantle.turn.completed", extra="iteration_count=2")])
        turns = v.analyse(rows)["turns"]
        self.assertEqual(len(turns), 2)
        self.assertEqual(turns[1]["orchestration"]["status"], "missing_boundary")

    def test_cold_load_is_distinct_from_process_or_codespace_start(self):
        rows = self.parse([self.line(0, "barge_in.nli_model.loading"),
                           self.line(6, "voice_channel.initialized"),
                           self.line(10, "Worker ready")])
        cold = v.analyse(rows)["cold_start"]
        self.assertEqual(cold["model_loading_to_voice_initialization"]["ms"], 6000)
        self.assertEqual(cold["capture_start_to_worker_line_observed"]["status"], "missing_boundary")

    def test_asr_configuration_is_not_an_asr_final_measurement(self):
        rows = self.parse([self.line(0, "asr.engine.initialized", extra="config={'endpointing': 400, 'utterance_end_ms': 1000}")])
        report = v.analyse(rows)
        self.assertEqual(report["asr_configurations"][0]["endpointing_ms"], 400)
        self.assertEqual(report["asr_configurations"][0]["utterance_end_ms"], 1000)
        self.assertEqual(report["end_of_speech_to_first_audio"]["count"], 0)

    def test_only_explicit_voice_sessions_enter_voice_context_summary(self):
        rows = self.parse([self.line(0, "processor.handle_voice_conversation.start", "voice"),
                           self.line(0, "mantle.turn.started", "voice"),
                           self.line(2, "mantle.turn.completed", "voice", "error=None iteration_count=2"),
                           self.line(3, "mantle.turn.started", "other"),
                           self.line(9, "mantle.turn.completed", "other", "error=None iteration_count=3")])
        report = v.analyse(rows)
        self.assertEqual(report["voice_session_orchestration"], {"count": 1, "p50_ms": 2000, "p95_ms": 2000})
        self.assertEqual(report["orchestration"]["count"], 2)

    def test_duplicate_json_keys_and_oversized_lines_are_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory) / "input"
            p.write_text('{"schema":"x","schema":"y"}\n')
            with self.assertRaises(ValueError):
                v.read_events(p, "events")
            p.write_text("x" * (v.MAX_LINE + 1))
            with self.assertRaises(ValueError):
                v.read_events(p, "sdk-log")


class CaptureControls(unittest.TestCase):
    def test_refused_group_probe_is_retained_without_retry_or_fallback(self):
        real_signal = os.killpg
        signals = []

        def probe(group, value):
            signals.append(value)
            if value == 0:
                raise PermissionError("authored refusal control")
            return real_signal(group, value)

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "timing.jsonl"
            with patch.object(v.os, "killpg", side_effect=probe):
                code = v.capture([sys.executable, "-c", "import time; time.sleep(30)"], output, .1)
            self.assertEqual(code, 126)
            self.assertEqual(signals, [signal.SIGTERM, 0])
            self.assertEqual(v.read_events(output, "events")[-1]["cleanup"], "permission_denied")

    def test_child_exit_code_and_timing_survive_without_retaining_stdout(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "timing.jsonl"
            child = "print('PRIVATE-STDOUT-CANARY'); print('2026-01-01 12:00:00 INFO Worker ready'); raise SystemExit(7)"
            result = subprocess.run([sys.executable, str(SCRIPT), "capture", "--output", str(output),
                                     "--", sys.executable, "-c", child], capture_output=True, timeout=10)
            self.assertEqual(result.returncode, 7, result.stderr)
            self.assertNotIn("PRIVATE", output.read_text())
            self.assertEqual(output.stat().st_mode & 0o777, 0o600)
            report = v.analyse(v.read_events(output, "events"))
            self.assertEqual(report["capture_exits"][0]["exit_code"], 7)
            self.assertEqual(report["cold_start"]["capture_start_to_worker_line_observed"]["status"], "observed")

    @unittest.skipUnless(os.name == "posix", "owned process groups require POSIX")
    def test_timeout_stops_the_owned_group_and_keeps_partial_artifact(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "timing.jsonl"
            child = ("import os,time; print('PID='+str(os.getpid()),flush=True); time.sleep(30)")
            result = subprocess.run([sys.executable, str(SCRIPT), "capture", "--timeout", ".2",
                                     "--output", str(output), "--", sys.executable, "-c", child],
                                    capture_output=True, timeout=10)
            self.assertEqual(result.returncode, 124, result.stderr)
            pid = int(result.stdout.decode().strip().split("PID=")[1])
            with self.assertRaises(ProcessLookupError):
                os.killpg(pid, 0)
            self.assertEqual(v.read_events(output, "events")[-1]["termination"], "timeout")

    @unittest.skipUnless(os.name == "posix", "owned process groups require POSIX")
    def test_stalled_stdout_sink_cannot_bypass_deadline_or_group_cleanup(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "timing.jsonl"
            pidfile = Path(directory) / "pid"
            child = ("import os,pathlib; pathlib.Path(" + repr(str(pidfile)) +
                     ").write_text(str(os.getpid())); os.write(1,b'x'*(16*1024*1024))")
            process = subprocess.Popen([sys.executable, str(SCRIPT), "capture", "--timeout", ".4",
                                        "--output", str(output), "--", sys.executable, "-c", child],
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            try:
                # Keep the pipe OPEN without draining it. communicate() would hide the bug.
                self.assertEqual(process.wait(timeout=5), 124)
                pid = int(pidfile.read_text())
                with self.assertRaises(ProcessLookupError):
                    os.killpg(pid, 0)
                self.assertEqual(v.read_events(output, "events")[-1]["termination"], "timeout")
            finally:
                if pidfile.exists():
                    try:
                        os.killpg(int(pidfile.read_text()), signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                if process.poll() is None:
                    process.kill()
                process.wait(timeout=5)
                process.stdout.close()
                process.stderr.close()

    def test_existing_capture_is_never_overwritten_or_rerun(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "timing.jsonl"
            output.write_text("original")
            result = subprocess.run([sys.executable, str(SCRIPT), "capture", "--output", str(output),
                                     "--", sys.executable, "-c", "raise SystemExit(99)"],
                                    capture_output=True, timeout=10)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(output.read_text(), "original")


if __name__ == "__main__":
    unittest.main()
