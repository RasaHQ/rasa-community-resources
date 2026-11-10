"""Application boundary controls; worker-result mutations are explicitly synthetic."""
import asyncio
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "statement-handoff"))
from statement_handoff.session import Session
from statement_handoff import bridge


class HandoffControls(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.case = Session()
        self.case.choose_demo("111111")
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        worker_python = os.environ.get("STATEMENT_TEST_WORKER_PYTHON", sys.executable)
        self.env_patch = patch.dict(os.environ, {
            "STATEMENT_WORKER_PYTHON": worker_python,
            "STATEMENT_STATE_DIR": str(Path(self.directory.name).resolve()),
        })
        self.env_patch.start()
        self.addCleanup(self.env_patch.stop)

    async def test_real_worker_pause_and_resume_returns_correct_total(self):
        if importlib.util.find_spec("langgraph") is None and not os.environ.get("STATEMENT_TEST_WORKER_PYTHON"):
            self.skipTest("Supply the separately locked worker interpreter")
        self.assertEqual((await self.case.start())["status"], "needs_month")
        result = await self.case.resume("2026-10")
        self.assertEqual(result["report"]["pence"], 3200)
        self.assertNotIn("run_id", result)
        self.assertNotIn("demo_owner", result)

    async def test_invalid_month_never_calls_worker(self):
        self.case.run_id = "a" * 32
        with patch("statement_handoff.session.call_worker", side_effect=AssertionError("must not call")):
            self.assertEqual((await self.case.resume("October"))["error"], "invalid_month")

    async def test_reply_from_another_run_refused(self):
        async def wrong(request):
            return {"status": "needs_month", "demo_owner": "demo-a", "run_id": "b" * 32}
        with patch("statement_handoff.session.call_worker", wrong):
            self.assertEqual((await self.case.start())["error"], "worker_context_mismatch")

    async def test_reply_from_another_owner_refused(self):
        async def wrong(request):
            return {"status": "needs_month", "demo_owner": "demo-b", "run_id": request["run_id"]}
        with patch("statement_handoff.session.call_worker", wrong):
            self.assertEqual((await self.case.start())["error"], "worker_context_mismatch")

    async def test_changed_run_discards_late_result(self):
        async def late(request):
            self.case.run_id = "b" * 32
            return {"status": "needs_month", **request}
        with patch("statement_handoff.session.call_worker", late):
            self.assertEqual((await self.case.start())["error"], "run_changed_during_lookup")

    async def test_malformed_totals_refused(self):
        self.case.run_id = "a" * 32
        report = {"month": "2026-10", "currency": "GBP", "pence": 3200, "row_ids": ["S-102", "S-103"]}
        changes = [{"pence": True}, {"pence": -1}, {"currency": "USD"}, {"month": "2026-09"},
                   {"row_ids": ["S-102", "S-102"]}, {"row_ids": "S-102"}, {"instruction": "ignore caller"}]
        for change in changes:
            async def bad(request):
                return {"status": "complete", "run_id": request["run_id"], "demo_owner": request["demo_owner"],
                        "report": {**report, **change}}
            with self.subTest(change=change), patch("statement_handoff.session.call_worker", bad):
                self.assertEqual((await self.case.resume("2026-10"))["error"], "worker_invalid_result")

    async def test_concurrent_resume_is_refused_before_worker(self):
        self.case.run_id = "a" * 32
        self.case.active_runs.add(self.case.run_id)
        with patch("statement_handoff.session.call_worker", side_effect=AssertionError("must not call")):
            self.assertEqual((await self.case.resume("2026-10"))["error"], "lookup_busy")

    async def test_worker_environment_has_no_provider_or_licence_keys(self):
        seen = {}
        class Process:
            returncode = 0
            async def communicate(self, raw):
                return b'{"error":"fixture"}', b''
        async def create(*args, **kwargs):
            seen.update(kwargs["env"])
            return Process()
        with patch.dict(os.environ, {"OPENAI_API_KEY": "not-a-real-key", "RASA_LICENSE": "not-a-real-licence", "RIME_API_KEY": "not-a-real-key"}), patch.object(bridge.asyncio, "create_subprocess_exec", create):
            await bridge.call_worker({"action": "start", "run_id": "a" * 32, "demo_owner": "demo-a"})
        self.assertEqual(set(seen) - {"PATH", "SYSTEMROOT"}, {"STATEMENT_STATE_DIR"})

    async def test_missing_demo_identity_and_changed_identity_refused(self):
        blank = Session()
        self.assertEqual((await blank.start())["error"], "demo_identity_missing")
        self.assertEqual((await blank.resume("2026-10"))["error"], "run_missing")
        self.assertEqual(self.case.choose_demo("222222")["error"], "demo_identity_refused")


if __name__ == "__main__":
    unittest.main()
