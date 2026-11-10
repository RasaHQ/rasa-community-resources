"""Offline negative controls for the text replay reader, not model qualification."""
import copy
import importlib.util
import json
import io
from pathlib import Path
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("replay_text", Path(__file__).resolve().parents[1] / "replay_text.py")
replay = importlib.util.module_from_spec(spec)
spec.loader.exec_module(replay)


def event(name, result, **extra):
    return {"event": "tool_executed", "tool_name": name, "result": json.dumps(result), "is_error": False, **extra}


def fixture():
    research = event("research_charge", {"status": "research_complete"})
    pause = event("submit_review", {"status": "awaiting_confirmation"})
    recorded = event("resolve_tool_confirmation", {"status": "demo_recorded", "transaction_id": "TX-101", "reference": "DEMO-TEST"})
    return [{"tracker": {"events": events}} for events in [[], [research], [research, pause], [research, pause, recorded]]]


class ReplayControls(unittest.TestCase):
    def test_duplicate_mcp_stream_does_not_double_count(self):
        turns = fixture()
        duplicate = copy.deepcopy(turns[-1]["tracker"]["events"][-1])
        duplicate["event"] = "mcp_tool_executed"
        turns[-1]["tracker"]["events"].append(duplicate)
        self.assertEqual(replay.validate("approval", turns)["recorded_results"], 1)

    def test_resolver_and_builder_events_share_one_receipt(self):
        turns = fixture()
        duplicate = copy.deepcopy(turns[-1]["tracker"]["events"][-1])
        duplicate["tool_name"] = "submit_review"
        turns[-1]["tracker"]["events"].append(duplicate)
        self.assertEqual(replay.validate("approval", turns)["recorded_results"], 1)

    def test_two_distinct_receipts_are_not_deduplicated(self):
        turns = fixture()
        turns[-1]["tracker"]["events"].append(event("submit_review", {"status": "demo_recorded", "transaction_id": "TX-101", "reference": "DEMO-SECOND"}))
        with self.assertRaisesRegex(AssertionError, "Wrong or missing"):
            replay.validate("approval", turns)

    def test_verbal_question_without_pause_is_not_success(self):
        turns = fixture()
        turns[2]["reply"] = [{"text": "Please confirm"}]
        turns[2]["tracker"]["events"] = turns[2]["tracker"]["events"][:1]
        with self.assertRaisesRegex(AssertionError, "not paused"):
            replay.validate("approval", turns)

    def test_same_turn_error_cannot_be_hidden_by_a_later_record(self):
        turns = fixture()
        turns[-1]["tracker"]["events"].append(event("resolve_tool_confirmation", {"error": "same turn"}, is_error=True))
        with self.assertRaisesRegex(AssertionError, "Runtime tool error"):
            replay.validate("approval", turns)

    def test_wrong_charge_receipt_is_refused(self):
        turns = fixture()
        turns[-1]["tracker"]["events"][-1]["result"] = json.dumps({"status": "demo_recorded", "transaction_id": "TX-102", "reference": "DEMO-WRONG"})
        with self.assertRaisesRegex(AssertionError, "Wrong or missing"):
            replay.validate("approval", turns)

    def test_denial_with_recorded_result_is_refused(self):
        with self.assertRaisesRegex(AssertionError, "Denial"):
            replay.validate("denial", fixture())

    def test_no_record_does_not_prove_research_succeeded(self):
        turns = fixture()
        turns[2]["tracker"]["events"][0]["result"] = json.dumps({"error": "worker_unavailable"})
        turns[-1]["tracker"]["events"] = []
        with self.assertRaisesRegex(AssertionError, "Research"):
            replay.validate("denial", turns)

    def test_empty_response_retains_partial_trace_and_does_not_retry(self):
        calls, saved = [], []
        def request(url, body):
            calls.append(url)
            return [] if body else {"events": []}
        with self.assertRaisesRegex(AssertionError, "No reply"):
            replay.replay("http://127.0.0.1:5005", "approval", request, saved.append)
        self.assertEqual(len(calls), 2)
        self.assertEqual(saved[-1]["status"], "incomplete")
        self.assertEqual(len(saved[-1]["turns"]), 1)

    def test_external_or_credentialled_origins_are_refused(self):
        for value in ["https://127.0.0.1", "http://example.com", "http://user:password@localhost", "http://localhost/path", "http://localhost?x=y"]:
            with self.assertRaises(ValueError):
                replay.local_base(value)
        self.assertEqual(replay.local_base("http://127.0.0.1:5005/"), "http://127.0.0.1:5005")

    def test_read_existing_trace_makes_no_network_request(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "approval.json"
            path.write_text(json.dumps({"case": "approval", "turns": fixture()}))
            with patch.object(sys, "argv", ["replay_text", "--case", "approval", "--read", str(path)]), patch.object(replay.urllib.request, "urlopen") as network, redirect_stdout(io.StringIO()):
                replay.main()
            network.assert_not_called()

    def test_existing_output_is_preserved_before_any_request(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "previous.json"
            path.write_text("keep this failure")
            with patch.object(sys, "argv", ["replay_text", "--case", "approval", "--out", str(path)]), patch.object(replay.urllib.request, "urlopen") as network:
                with self.assertRaises(FileExistsError):
                    replay.main()
            network.assert_not_called()
            self.assertEqual(path.read_text(), "keep this failure")


if __name__ == "__main__":
    unittest.main()
