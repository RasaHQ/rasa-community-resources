"""Native LangGraph/SQLite controls; no mock graph and no model requests."""
import json
import ast
import inspect
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import textwrap
import unittest
from unittest.mock import patch

from statement_worker.worker import handle


class CheckpointControls(unittest.TestCase):
    def setUp(self):
        self.connection = sqlite3.connect(":memory:", check_same_thread=False)
        self.addCleanup(self.connection.close)
        self.context = {"run_id": "a" * 32, "demo_owner": "demo-a"}

    def call(self, action, **kwargs):
        return handle({**self.context, "action": action, **kwargs}, self.connection)

    def test_pause_then_resume_keeps_first_read(self):
        self.assertEqual(self.call("start")["status"], "needs_month")
        with patch("statement_worker.graph.load_rows", side_effect=AssertionError("read repeated")):
            result = self.call("resume", month="2026-10")
        self.assertEqual(result["report"], {
            "month": "2026-10", "currency": "GBP", "pence": 3200, "row_ids": ["S-102", "S-103"]})

    def test_invalid_answer_does_not_consume_pause(self):
        self.call("start")
        self.assertEqual(self.call("resume", month="2026-13")["error"], "invalid_month")
        self.assertEqual(self.call("resume", month="2026-09")["report"]["pence"], 14900)

    def test_other_demo_owner_cannot_resume_existing_run(self):
        self.call("start")
        self.assertEqual(self.call("resume", demo_owner="demo-b", month="2026-10"), {"error": "context_mismatch"})

    def test_removing_owner_check_returns_original_rows_labelled_as_new_owner(self):
        # Controlled mutation of the actual handler, never a service option.
        import statement_worker.worker as module
        tree = ast.parse(textwrap.dedent(inspect.getsource(handle)))
        body = tree.body[0].body
        matched = [node for node in body if isinstance(node, ast.If)
                   and "previous.values.get('demo_owner')" in ast.unparse(node.test)]
        self.assertEqual(len(matched), 1)
        body.remove(matched[0])
        namespace = dict(vars(module))
        exec(compile(ast.fix_missing_locations(tree), "<owner-check-removal-control>", "exec"), namespace)
        self.call("start")
        result = namespace["handle"]({**self.context, "action": "resume", "demo_owner": "demo-b", "month": "2026-10"}, self.connection)
        self.assertEqual(result["demo_owner"], "demo-b")
        self.assertEqual(result["report"]["row_ids"], ["S-102", "S-103"])
        self.assertEqual(result["report"]["pence"], 3200)
        print("owner check removed | requested=demo-b | checkpoint=demo-a | returned=S-102,S-103/3200 pence")

    def test_missing_run_is_not_started_by_a_resume(self):
        self.assertEqual(self.call("resume", month="2026-10"), {"error": "run_missing"})

    def test_two_runs_do_not_share_a_month_or_rows(self):
        self.call("start")
        other = {"action": "start", "run_id": "b" * 32, "demo_owner": "demo-b"}
        handle(other, self.connection)
        result = handle({**other, "action": "resume", "month": "2026-10"}, self.connection)
        self.assertEqual(result["report"]["row_ids"], ["S-201"])
        self.assertEqual(self.call("start")["status"], "needs_month")

    def test_repeat_resume_returns_same_result_and_correction_needs_new_run(self):
        self.call("start")
        result = self.call("resume", month="2026-10")
        self.assertEqual(self.call("resume", month="2026-10"), result)
        self.assertEqual(self.call("resume", month="2026-09")["error"], "completed_month_changed")

    def test_database_survives_separate_worker_processes_without_provider_keys(self):
        with tempfile.TemporaryDirectory() as directory:
            env = {"PATH": os.environ["PATH"], "STATEMENT_STATE_DIR": str(Path(directory).resolve())}
            def invoke(action, **extra):
                result = subprocess.run([sys.executable, "-B", "-m", "statement_worker.worker"],
                    input=json.dumps({**self.context, "action": action, **extra}),
                    text=True, capture_output=True, env=env, timeout=10)
                self.assertEqual(result.returncode, 0, result.stderr)
                return json.loads(result.stdout)
            self.assertEqual(invoke("start")["status"], "needs_month")
            self.assertEqual(invoke("resume", month="2026-10")["report"]["pence"], 3200)
            self.assertEqual((Path(directory) / "checkpoints.sqlite").stat().st_mode & 0o777, 0o600)

    def test_new_thread_is_the_failing_restart_control(self):
        self.call("start")
        result = self.call("resume", run_id="b" * 32, month="2026-10")
        self.assertEqual(result["error"], "run_missing")

    def test_reader_cli_preserves_virtualenv_interpreter(self):
        with tempfile.TemporaryDirectory() as directory:
            script = Path(__file__).resolve().parents[2] / "demo_statement.py"
            result = subprocess.run([sys.executable, "-B", str(script), "--worker-python", sys.executable,
                "--state-dir", directory, "--month", "2026-10"], capture_output=True, text=True, timeout=15,
                env={"PATH": os.environ["PATH"]})
            self.assertEqual(result.returncode, 0, result.stderr)
            lines = [json.loads(line) for line in result.stdout.splitlines()]
            self.assertEqual(lines[0]["status"], "needs_month")
            self.assertEqual(lines[1]["report"]["pence"], 3200)

    def test_unknown_action_and_extra_input_refused(self):
        self.assertEqual(self.call("override"), {"error": "unknown_action"})
        self.assertEqual(self.call("start", account_override="real-account"), {"error": "unexpected_input"})


if __name__ == "__main__":
    unittest.main()
