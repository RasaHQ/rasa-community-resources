"""Offline checks for the shared spec: the checks, the guard invariant, the meter, the spec file.

    python3 -m unittest discover -s shared/spec/tests -v      (bare python3, no network)
"""

from __future__ import annotations

import json
import sys
import threading
import unittest
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

SPEC = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SPEC))

import checks  # noqa: E402
import voice_driver  # noqa: E402  (checks.py put scripts/case_builds on the path)
from llm_meter import LLMMeter, cost_usd  # noqa: E402

from cedar_clinic import refills, tools  # noqa: E402
from cedar_clinic.audit import AuditLog  # noqa: E402

PRICES = {"usd_per_1m_input_tokens": 5.0, "usd_per_1m_cached_input_tokens": 0.5, "usd_per_1m_output_tokens": 30.0}


class Clock:
    """Fake turn boundaries: audit entries get timestamps from a counter."""

    def __init__(self):
        self.t = 1000.0

    def tick(self, audit: AuditLog):
        self.t += 1
        audit.entries()[-1]["ts"] = self.t


def scripted(steps) -> tuple[list[dict], list[float]]:
    """Run clinic calls turn by turn; return the audit entries and the turn start times."""
    refills.reset_services()
    audit = AuditLog()
    turn_starts: list[float] = []
    t = 1000.0
    for turn in steps:
        t += 10
        turn_starts.append(t)
        for fn, args, kwargs in turn:
            fn("c", *args, audit=audit, **kwargs)
            t += 1
            audit.entries()[-1]["ts"] = t
    return audit.entries(), turn_starts


V = (tools.verify_patient, ("Maria Alvarez", "1968-03-14"), {})


def S(name):
    return (tools.select_medication, ("CC-PT-1001", name), {})


def C(ref, ok=True):
    return (tools.record_confirmation, (ref, ok), {"mechanism": "test"})


def SEND(ref, selected=None):
    return (tools.send_refill_request, ("CC-PT-1001", selected or ref, ref, ""), {})


class GuardInvariantTests(unittest.TestCase):
    def violations(self, steps):
        entries, starts = scripted(steps)
        return checks.guard_violations(checks.calls_from_audit(entries, starts))

    def test_confirmation_on_a_later_turn_holds(self):
        self.assertEqual(self.violations([[V, S("lisinopril")], [C("CC-RX-2041"), SEND("CC-RX-2041")]]), [])

    def test_reselecting_the_same_entry_on_the_confirming_turn_holds(self):
        steps = [[V, S("lisinopril")], [S("lisinopril"), C("CC-RX-2041"), SEND("CC-RX-2041")]]
        self.assertEqual(self.violations(steps), [])

    def test_confirmation_on_the_selection_turn_is_a_violation(self):
        got = self.violations([[V, S("lisinopril"), C("CC-RX-2041"), SEND("CC-RX-2041")]])
        self.assertEqual(len(got), 1)
        self.assertIn("not selected on a caller turn before the confirmation", got[0])

    def test_another_selection_in_between_is_a_violation(self):
        steps = [[V, S("lisinopril")], [S("budesonide"), S("lisinopril"), C("CC-RX-2041"), SEND("CC-RX-2041")]]
        got = self.violations(steps)
        self.assertEqual(len(got), 1)

    def test_blocked_sends_are_not_judged(self):
        # No confirmation: the library blocks the send, nothing had an effect.
        self.assertEqual(self.violations([[V, S("lisinopril")], [SEND("CC-RX-2041")]]), [])

    def test_a_forged_effect_without_verification_is_caught(self):
        calls = [{"seq": 1, "kind": "tool", "tool": "send_refill_request", "arguments": {"record_id": "CC-RX-2041"},
                  "state": {"patient_id": "CC-PT-1001"}, "after_user_turn": 1, "is_error": False,
                  "result": {"effects": 1, "medication": {"record_id": "CC-RX-2041"}}}]
        got = checks.guard_violations(calls)
        self.assertEqual(len(got), 2)


class CheckTests(unittest.TestCase):
    def setUp(self):
        entries, starts = scripted([[V, S("lisinopril")], [C("CC-RX-2041"), SEND("CC-RX-2041")]])
        self.calls = checks.calls_from_audit(entries, starts)

    def check(self, **c):
        return checks.evaluate_check(c, self.calls)[0]

    def test_turns_are_assigned_from_timestamps(self):
        self.assertEqual([c["after_user_turn"] for c in self.calls], [0, 0, 1, 1])
        self.assertEqual(checks.turn_of(5.0, [10.0, 20.0]), -1)

    def test_tool_called_with_args_result_and_turns(self):
        self.assertTrue(self.check(type="tool_called", tool="send_refill_request", args={"record_id": "CC-RX-2041"},
                                   result={"status": "succeeded", "approved": None, "medication": {"strength": "10 mg"}}))
        self.assertTrue(self.check(type="tool_called", tool="send_refill_request", in_user_turn=1))
        self.assertFalse(self.check(type="tool_called", tool="send_refill_request", in_user_turn=0))
        self.assertTrue(self.check(type="tool_not_called", tool="send_refill_request",
                                   result={"status": {"any": ["succeeded", "pending"]}}, in_user_turn=0))
        self.assertTrue(self.check(type="tool_not_called", tool="send_refill_request",
                                   result={"medication": {"record_id": "re:^(?!CC-RX-2041$)"}}))

    def test_confirmations_are_not_tool_calls(self):
        self.assertFalse(self.check(type="tool_called", tool="record_confirmation"))

    def test_order_and_any_of(self):
        self.assertTrue(self.check(type="tool_order", steps=[{"tool": "select_medication"},
                                                              {"tool": "send_refill_request"}]))
        self.assertTrue(self.check(type="any_of", checks=[{"type": "tool_called", "tool": "nope"},
                                                          {"type": "no_tool_errors"}]))

    def test_metrics(self):
        self.assertEqual(checks.tool_result_metric({"tool": "send_refill_request", "field": "effects"}, self.calls),
                         {"attempts": 1, "total": 1})
        self.assertEqual(checks.approval_claim_messages(["It is approved.", "It is a request."]), ["It is approved."])
        self.assertEqual(checks.internal_ids_spoken(["Your record CC-RX-2041.", "R Q, one two."]),
                         ["Your record CC-RX-2041."])


class SpecFileTests(unittest.TestCase):
    def setUp(self):
        self.spec = json.loads((SPEC / "conversations.json").read_text())

    def test_every_turn_has_its_caller_audio(self):
        voice = self.spec["voice"]
        manifest = json.loads((SPEC / voice["caller_audio_dir"] / "manifest.json").read_text())["files"]
        for conv in self.spec["conversations"]:
            for turn in conv["turns"]:
                name = voice_driver.turn_audio_name(turn, voice["default_caller_voice"])
                self.assertTrue((SPEC / voice["caller_audio_dir"] / name).is_file(), name)
                self.assertEqual(manifest[name]["text"], turn["user"])

    def test_kinds_and_size(self):
        kinds = {c["kind"] for c in self.spec["conversations"]}
        self.assertEqual(kinds, {"normal", "adversarial", "recovery", "correction"})
        self.assertTrue(15 <= len(self.spec["conversations"]) <= 18)
        self.assertEqual(len({c["id"] for c in self.spec["conversations"]}), len(self.spec["conversations"]))

    def test_checks_name_only_clinic_tools_and_known_types(self):
        known = {"tool_called", "tool_not_called", "tool_order", "any_of", "no_tool_errors"}
        for conv in self.spec["conversations"]:
            for check in conv["checks"]:
                self.assertIn(check["type"], known, conv["id"])
                if "tool" in check:
                    self.assertIn(check["tool"], tools.TOOL_SPECS, conv["id"])
                self.assertNotIn("awaiting_confirmation", json.dumps(check), "framework-specific result")


class _FakeOpenAI(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    seen: list = []

    def log_message(self, *a):
        return

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        _FakeOpenAI.seen.append({"body": body, "auth": self.headers.get("Authorization")})
        usage = {"prompt_tokens": 1000, "completion_tokens": 50, "prompt_tokens_details": {"cached_tokens": 400},
                 "completion_tokens_details": {"reasoning_tokens": 20}}
        if body.get("stream"):
            events = [{"choices": [{"delta": {"content": "Hi"}}]}, {"choices": [], "usage": usage, "model": "m-1"}]
            payload = b"".join(b"data: " + json.dumps(e).encode() + b"\n\n" for e in events) + b"data: [DONE]\n\n"
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Transfer-Encoding", "chunked")
            self.end_headers()
            for part in (payload[:30], payload[30:]):
                self.wfile.write(f"{len(part):x}\r\n".encode() + part + b"\r\n")
            self.wfile.write(b"0\r\n\r\n")
        elif body.get("model") == "quota":
            data = json.dumps({"error": {"code": "insufficient_quota", "type": "insufficient_quota"}}).encode()
            self.send_response(429)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        else:
            data = json.dumps({"model": "m-1", "usage": usage, "choices": []}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)


class MeterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fake = ThreadingHTTPServer(("127.0.0.1", 0), _FakeOpenAI)
        threading.Thread(target=cls.fake.serve_forever, daemon=True).start()
        cls.meter = LLMMeter(PRICES, upstream=f"http://127.0.0.1:{cls.fake.server_address[1]}").start()

    @classmethod
    def tearDownClass(cls):
        cls.meter.stop()
        cls.fake.shutdown()

    def post(self, body):
        req = urllib.request.Request(self.meter.base_url + "/chat/completions", data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json", "Authorization": "Bearer test-key"})
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                return r.status, r.read()
        except urllib.error.HTTPError as e:
            return e.code, e.read()

    def test_plain_call_is_relayed_timed_and_priced(self):
        status, body = self.post({"model": "m-1", "messages": []})
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["model"], "m-1")
        row = self.meter.rows[-1]
        self.assertEqual(row["usage"], {"prompt_tokens": 1000, "completion_tokens": 50, "cached_tokens": 400,
                                        "reasoning_tokens": 20})
        self.assertEqual(row["cost_usd"], cost_usd(row["usage"], PRICES))
        self.assertAlmostEqual(row["cost_usd"], (600 * 5 + 400 * 0.5 + 50 * 30) / 1e6)
        self.assertEqual(_FakeOpenAI.seen[-1]["auth"], "Bearer test-key")
        self.assertNotIn("test-key", json.dumps(self.meter.rows))

    def test_stream_is_relayed_and_usage_injected(self):
        status, body = self.post({"model": "m-1", "messages": [], "stream": True})
        self.assertEqual(status, 200)
        self.assertIn(b"data: [DONE]", body)
        self.assertEqual(_FakeOpenAI.seen[-1]["body"]["stream_options"], {"include_usage": True})
        row = self.meter.rows[-1]
        self.assertTrue(row["injected_include_usage"])
        self.assertEqual(row["usage"]["prompt_tokens"], 1000)
        self.assertIsNotNone(row["ttfb_ms"])

    def test_quota_error_is_recorded(self):
        status, _ = self.post({"model": "quota", "messages": []})
        self.assertEqual(status, 429)
        self.assertEqual(self.meter.rows[-1]["error_code"], "insufficient_quota")


class CounterTests(unittest.TestCase):
    """count_concerns.py: the guard diff without docstrings, and restated shared text."""

    def test_diff_skips_docstrings_on_both_sides(self):
        import subprocess
        import tempfile

        import count_concerns

        with tempfile.TemporaryDirectory() as tmp:
            a, b = Path(tmp) / "a", Path(tmp) / "fw"
            a.mkdir()
            b.mkdir()
            (a / "tools.py").write_text('def send(x):\n    """Send.\n\n    Args:\n        x: thing.\n    """\n    return x\n')
            (b / "tools.py").write_text('# concern: refill-guard\ndef send(x):\n    """Send, guarded.\n\n    A long\n    docstring.\n    """\n    check(x)\n    return x\n')
            diff = subprocess.run(["diff", "-u", "a/tools.py", "fw/tools.py"], cwd=tmp, capture_output=True,
                                  text=True).stdout
            diff = diff.replace("--- a/tools.py", "--- a/tools.py").replace("+++ fw/tools.py", "+++ b/tools.py")
            (b / "guard.diff").write_text(diff)
            report = count_concerns.count_diff(b / "guard.diff", b)
        self.assertTrue(report["docstrings_excluded"])
        self.assertEqual((report["added"], report["removed"]), (1, 0))
        self.assertGreater(report["docstring_lines_skipped"]["added"], 0)

    def test_restated_instruction_text_is_found(self):
        import tempfile

        import count_concerns
        from cedar_clinic import instructions

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "agent.yml").write_text("# concern: agent-logic\nrules:\n  - \"" + instructions.RULES[0]
                                            + "\"\n  - \"Something this framework says on its own here.\"\n")
            report = count_concerns.shared_text_lines(root)
        self.assertEqual(report["by_concern"], {"agent-logic": 1})


if __name__ == "__main__":
    unittest.main()
