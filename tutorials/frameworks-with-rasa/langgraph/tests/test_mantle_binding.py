"""Actual Mantle tool bindings with a controlled session; no model conversation."""
import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "statement-handoff"))
from statement_handoff.session import Session


@unittest.skipUnless(importlib.util.find_spec("rasa"), "Run with the locked Mantle interpreter")
class MantleBindings(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        path = ROOT / "langgraph-mantle/skills/statement_search/tools.py"
        spec = importlib.util.spec_from_file_location("statement_tools", path)
        self.tools = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.tools)
        self.case = Session()
        self.patcher = patch.object(self.tools, "session", return_value=self.case)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)

    async def test_native_binding_does_not_expose_run_or_owner_parameters(self):
        import inspect
        self.assertEqual(set(inspect.signature(self.tools.answer_statement_month).parameters), {"month", "context"})
        self.assertEqual(set(inspect.signature(self.tools.start_statement_lookup).parameters), {"context"})

    async def test_native_binding_refuses_missing_identity(self):
        result = await self.tools.start_statement_lookup()
        self.assertEqual(result.llm_response["error"], "demo_identity_missing")

    async def test_native_binding_returns_pause_then_validated_report(self):
        async def reply(request):
            if request["action"] == "start":
                return {"status": "needs_month", "run_id": request["run_id"], "demo_owner": request["demo_owner"]}
            return {"status": "complete", "run_id": request["run_id"], "demo_owner": request["demo_owner"],
                    "report": {"month": "2026-10", "currency": "GBP", "pence": 3200, "row_ids": ["S-102", "S-103"]}}
        with patch("statement_handoff.session.call_worker", reply):
            self.assertEqual((await self.tools.select_demo("111111")).llm_response["status"], "demo_selected")
            self.assertEqual((await self.tools.start_statement_lookup()).llm_response["status"], "needs_month")
            result = await self.tools.answer_statement_month("2026-10")
        self.assertEqual(result.llm_response["report"]["pence"], 3200)
        self.assertNotIn("run_id", result.llm_response)

    async def test_real_worker_reached_through_native_tool(self):
        import os
        import tempfile
        if not os.environ.get("STATEMENT_TEST_WORKER_PYTHON"):
            self.skipTest("Supply the separately locked worker interpreter")
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {
            "STATEMENT_WORKER_PYTHON": os.environ["STATEMENT_TEST_WORKER_PYTHON"],
            "STATEMENT_STATE_DIR": str(Path(directory).resolve()),
        }):
            await self.tools.select_demo("111111")
            self.assertEqual((await self.tools.start_statement_lookup()).llm_response["status"], "needs_month")
            result = await self.tools.answer_statement_month("2026-10")
        self.assertEqual(result.llm_response["report"]["row_ids"], ["S-102", "S-103"])


if __name__ == "__main__":
    unittest.main()
