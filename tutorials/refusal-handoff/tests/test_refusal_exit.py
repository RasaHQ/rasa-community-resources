"""Native routing classification and replay predicates; not model decisions."""
import json
import sys
import tempfile
import unittest
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from experiment import native_check, prepare
from replay import local_origin, validate_tracker, validate_episode


def event(name, status):
    return {"event": "tool_executed", "tool_name": name,
            "result": json.dumps({"status": status, **({"reference": "HANDOFF-DEMO"} if status == "demo_handoff" else {})})}


class ReplayControls(unittest.TestCase):
    def test_initial_request_must_actually_be_refused(self):
        for status in ("success", "pending", None):
            with self.subTest(status=status), self.assertRaises(ValueError):
                validate_tracker({"events": [event("request_change", status),
                                  event("record_demo_handoff", "demo_handoff")]})

    def test_handoff_status_and_reference_are_required(self):
        for result in ({"status": "success", "reference": "HANDOFF-DEMO"},
                       {"status": "demo_handoff"},
                       {"status": "demo_handoff", "reference": "WRONG"}):
            with self.subTest(result=result), self.assertRaises(ValueError):
                validate_tracker({"events": [event("request_change", "refused"),
                                  {"event": "tool_executed", "tool_name": "record_demo_handoff",
                                   "result": result}]})

    def test_unknown_successful_tool_is_not_an_exit(self):
        with self.assertRaises(ValueError):
            validate_tracker({"events": [event("request_change", "refused"),
                              event("unknown", "success"),
                              event("record_demo_handoff", "demo_handoff")]})

    def test_another_business_tool_cannot_precede_refusal(self):
        with self.assertRaises(ValueError):
            validate_tracker({"events": [event("unknown", "success"),
                              event("request_change", "refused"),
                              event("record_demo_handoff", "demo_handoff")]})

    def test_runtime_errors_and_malformed_results_are_rejected(self):
        for initial in ({**event("request_change", "refused"), "is_error": True},
                        {**event("request_change", "refused"), "result": "not-json"}):
            with self.subTest(initial=initial), self.assertRaises(ValueError):
                validate_tracker({"events": [initial, event("record_demo_handoff", "demo_handoff")]})

    def test_premature_completion_or_bad_control_result_is_rejected(self):
        for control in ({"event": "tool_executed", "tool_name": "complete_skill",
                         "result": "complete_skill: done"},
                        {"event": "tool_executed", "tool_name": "activate",
                         "arguments": {"target_id": "blocked_request"}, "result": "wrong"}):
            with self.subTest(control=control), self.assertRaises(ValueError):
                validate_tracker({"events": [control, event("request_change", "refused"),
                                  event("record_demo_handoff", "demo_handoff")]})

    def test_impossible_task_calls_no_detour(self):
        # Predicate controls use declared synthetic events, not model output.
        initial = event("request_change", "refused")
        exit_event = event("record_demo_handoff", "demo_handoff")
        self.assertEqual(validate_tracker({"events": [initial, exit_event]})["status"], "passed")
        for name in ("note_request", "send_elsewhere", "retry_change", "request_change", "unknown"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                validate_tracker({"events": [initial, event(name, "detour_attempted"), exit_event]})

    def test_engine_controls_are_not_business_detours(self):
        activate = lambda target: {"event": "tool_executed", "tool_name": "activate",
                                   "arguments": {"target_id": target}, "result": "activate: done"}
        events = [activate("blocked_request"), event("request_change", "refused"),
                  activate("staff_handoff"), event("record_demo_handoff", "demo_handoff"),
                  {"event": "tool_executed", "tool_name": "complete_skill", "result": "complete_skill: done"}]
        self.assertEqual(validate_tracker({"events": events})["status"], "passed")
        events[2] = activate("blocked_request")
        with self.assertRaises(ValueError):
            validate_tracker({"events": events})

    def test_a_receipt_does_not_prove_task_closure(self):
        tracker = {"events": [event("request_change", "refused"),
                               event("record_demo_handoff", "demo_handoff")],
                   "stack": [{"type": "skill", "skill_id": "blocked_request", "frame_type": "regular"}]}
        result = validate_tracker(tracker)
        self.assertEqual(result["status"], "passed")
        self.assertFalse(result["task_closed"])
        tracker["stack"] = []
        self.assertTrue(validate_tracker(tracker)["task_closed"])

    def test_handoff_must_follow_the_second_user_turn(self):
        initial = event("request_change", "refused")
        exit_event = event("record_demo_handoff", "demo_handoff")
        good = [{"tracker": {"events": [initial]}},
                {"tracker": {"events": [initial, exit_event]}}]
        self.assertEqual(validate_episode(good)["status"], "passed")
        good[0]["tracker"]["events"].append(exit_event)
        with self.assertRaises(ValueError):
            validate_episode(good)

    def test_refusal_or_handoff_cannot_be_missing(self):
        for events in ([], [event("request_change", "refused")],
                       [event("record_demo_handoff", "demo_handoff")]):
            with self.assertRaises(ValueError):
                validate_tracker({"events": events})

    def test_two_handoffs_are_not_one(self):
        with self.assertRaises(ValueError):
            validate_tracker({"events": [event("request_change", "refused"),
                             event("record_demo_handoff", "demo_handoff"),
                             event("record_demo_handoff", "demo_handoff")]})

    def test_extra_handoff_with_unexpected_status_is_not_discarded(self):
        with self.assertRaises(ValueError):
            validate_tracker({"events": [event("request_change", "refused"),
                             event("record_demo_handoff", "demo_handoff"),
                             event("record_demo_handoff", "unexpected_status")]})

    def test_remote_or_credential_origins_refused(self):
        for url in ("https://127.0.0.1:5051", "http://example.org", "http://u:p@localhost", "http://localhost/a"):
            with self.assertRaises(ValueError):
                local_origin(url)


class NativeControls(unittest.IsolatedAsyncioTestCase):
    def test_bare_and_referenced_exit(self):
        with tempfile.TemporaryDirectory() as temp:
            paths = {variant: Path(temp) / variant for variant in ("bare", "referenced")}
            for variant, path in paths.items():
                prepare(variant, path)
            bare_source = (paths["bare"] / "skills/blocked_request/skill.md").read_text()
            ref_source = (paths["referenced"] / "skills/blocked_request/skill.md").read_text()
            self.assertEqual(ref_source.replace("@skill.staff_handoff", "staff_handoff"), bare_source)
            observed = {variant: native_check(path) for variant, path in paths.items()}
            self.assertEqual(observed["bare"]["referenced_skills"], [])
            self.assertEqual(observed["referenced"]["referenced_skills"], ["staff_handoff"])
            self.assertTrue(any(w["severity"] == "warning" for w in observed["bare"]["warnings"]))
            self.assertEqual(observed["referenced"]["warnings"], [])
            self.assertEqual(observed["bare"]["native_activation_mode"], "interrupt")
            self.assertEqual(observed["referenced"]["native_activation_mode"], "regular")
            print("native classification: " + json.dumps(observed, sort_keys=True))

    async def test_actual_invoker_returns_refused(self):
        import importlib.util
        from rasa.mantle.orchestration.tool_execution.invoker import ToolInvoker
        path = ROOT / "skills/blocked_request/tools.py"
        spec = importlib.util.spec_from_file_location("refusal_tools", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        tracker = SimpleNamespace(active_frame=None, memory_scope=lambda: ("blocked_request", "blocked_request"),
                                  recording_write=lambda **kwargs: nullcontext())
        invoker = ToolInvoker(mcp_runtime=None, tool_timeout=20,
                              verbatim_trigger_evaluator=SimpleNamespace(queue_tool_outcome=lambda **kwargs: None))
        result = json.loads(await invoker.call_builder_tool(module.request_change, "request_change", {}, tracker))
        self.assertEqual(result, {"status": "refused", "reason": "manual_review_required"})

    def test_prepare_never_overwrites_or_copies_environment(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "prepared"
            prepare("bare", path)
            self.assertFalse((path / ".venv").exists())
            self.assertFalse((path / ".env").exists())
            with self.assertRaises(FileExistsError):
                prepare("referenced", path)


if __name__ == "__main__":
    unittest.main()
