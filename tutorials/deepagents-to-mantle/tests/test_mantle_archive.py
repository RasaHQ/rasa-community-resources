"""Cold native archive load; optional only when the Rasa SDK is not installed."""
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

PROJECT = Path(__file__).resolve().parents[1] / "mantle"


@unittest.skipUnless(importlib.util.find_spec("rasa"), "Run with the locked Mantle interpreter for native archive qualification")
class ColdMantleArchive(unittest.TestCase):
    def test_archive_loads_without_a_warm_shared_import(self):
        from rasa.mantle.model_archive.snapshot import package_model_archive
        with tempfile.TemporaryDirectory() as temp:
            result = package_model_archive(str(PROJECT / "agent.yml"), temp, fixed_model_name="cold-chat", validate=True)
            self.assertEqual(result.code, 0)
            env = {k: v for k, v in os.environ.items() if not k.endswith("_API_KEY") and k not in {"RASA_PRO_LICENSE", "RASA_LICENSE", "PYTHONPATH"}}
            env.update(RASA_TELEMETRY_ENABLED="false", LITELLM_LOCAL_MODEL_COST_MAP="True")
            code = "import asyncio; from rasa.core.agent import Agent; from rasa.core.config.configuration import Configuration; Configuration.initialise_endpoints(None); a=Agent.load(__import__('sys').argv[1]); asyncio.run(a.close()); print('cold archive load: ok')"
            process = subprocess.run([sys.executable, "-B", "-c", code, result.model], cwd=temp, env=env, capture_output=True, text=True, timeout=90)
            self.assertEqual(process.returncode, 0, process.stderr)
            self.assertIn("cold archive load: ok", process.stdout)

    def test_target_loads_and_invokes_with_deepagents_imports_blocked(self):
        from rasa.mantle.model_archive.snapshot import package_model_archive
        with tempfile.TemporaryDirectory() as temp:
            result = package_model_archive(str(PROJECT / "agent.yml"), temp, fixed_model_name="mantle-only", validate=True)
            self.assertEqual(result.code, 0)
            env = {k: v for k, v in os.environ.items() if not k.endswith("_API_KEY") and k not in {"RASA_PRO_LICENSE", "RASA_LICENSE", "PYTHONPATH"}}
            env.update(RASA_TELEMETRY_ENABLED="false", LITELLM_LOCAL_MODEL_COST_MAP="True")
            code = r"""
import asyncio, importlib.abc, importlib.util, json, os, sqlite3, sys
from pathlib import Path
from contextlib import nullcontext, closing
from types import SimpleNamespace
class NoDeepAgents(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "deepagents" or fullname.startswith("deepagents."):
            raise ModuleNotFoundError("Deep Agents deliberately unavailable")
assert not any(n == "deepagents" or n.startswith("deepagents.") for n in sys.modules)
sys.meta_path.insert(0, NoDeepAgents())
try:
    import deepagents
except ModuleNotFoundError as error:
    assert str(error) == "Deep Agents deliberately unavailable"
else:
    raise AssertionError("Import blocker did not run")
from rasa.core.agent import Agent
from rasa.core.config.configuration import Configuration
from rasa.mantle.orchestration.tool_execution.invoker import ToolInvoker
Configuration.initialise_endpoints(None)
agent = Agent.load(sys.argv[1])
path = Path("sample.sqlite")
with closing(sqlite3.connect(path)) as db:
    db.execute("CREATE TABLE Example(value INTEGER)")
    db.commit()
os.environ["CHINOOK_DATABASE"] = str(path.resolve())
spec = importlib.util.spec_from_file_location("migration_query_binding", sys.argv[2])
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
async def run():
    tracker = SimpleNamespace(memory_scope=lambda: ("query_store", "query_store"), recording_write=lambda **kwargs: nullcontext())
    invoker = ToolInvoker(mcp_runtime=None, tool_timeout=10, verbatim_trigger_evaluator=None)
    value = json.loads(await invoker.call_tool_func(module.sql_db_query, "sql_db_query", {"query": "SELECT 1 AS one"}, tracker))
    assert value["status"] == "ok" and value["rows"] == [[1]], value
    await agent.close()
asyncio.run(run())
assert not any(n == "deepagents" or n.startswith("deepagents.") for n in sys.modules)
print("Mantle-only cold load and native query: ok; Deep Agents imports blocked")
"""
            process = subprocess.run([sys.executable, "-B", "-c", code, result.model, str(PROJECT / "skills/query_store/tools.py")], cwd=temp, env=env, capture_output=True, text=True, timeout=90)
            self.assertEqual(process.returncode, 0, process.stderr)
            self.assertIn("Mantle-only cold load and native query: ok", process.stdout)
            print("Mantle-only cold load and native query: ok; Deep Agents imports blocked")

    def test_warm_import_does_not_prove_cold_dependency_availability(self):
        from rasa.mantle.model_archive.snapshot import package_model_archive
        with tempfile.TemporaryDirectory() as temp:
            result = package_model_archive(str(PROJECT / 'agent.yml'), temp, fixed_model_name='dependency-check', validate=True)
            self.assertEqual(result.code, 0)
            env = {k: v for k, v in os.environ.items() if not k.endswith('_API_KEY') and k not in {'RASA_PRO_LICENSE', 'RASA_LICENSE', 'PYTHONPATH'}}
            env.update(RASA_TELEMETRY_ENABLED='false', LITELLM_LOCAL_MODEL_COST_MAP='True')
            code = """
import asyncio, importlib.abc, sys
from rasa.core.agent import Agent
from rasa.core.config.configuration import Configuration
from rasa.exceptions import ValidationError
from rasa.mantle.tools.loader import ToolLoadingError
Configuration.initialise_endpoints(None)
mode = sys.argv[2]
if mode == 'warm':
    from shared import database
class MissingShared(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == 'shared' or fullname.startswith('shared.'):
            raise ModuleNotFoundError('injected missing shared dependency')
sys.meta_path.insert(0, MissingShared())
try:
    agent = Agent.load(sys.argv[1])
except ValidationError as error:
    cause = error.__cause__
    if mode != 'cold' or not isinstance(cause, ToolLoadingError) or 'injected missing shared dependency' not in str(cause):
        raise
    print('cold: missing dependency refused')
else:
    asyncio.run(agent.close())
    if mode != 'warm':
        raise AssertionError('Cold model unexpectedly loaded with dependency unavailable')
    print('warm: cached dependency hides the fault')
"""
            for mode, expected in [('warm', 'warm: cached dependency hides the fault'), ('cold', 'cold: missing dependency refused')]:
                process = subprocess.run([sys.executable, '-B', '-c', code, result.model, mode], cwd=temp, env=env, capture_output=True, text=True, timeout=90)
                self.assertEqual(process.returncode, 0, process.stderr)
                self.assertIn(expected, process.stdout)
                print(expected)

@unittest.skipUnless(importlib.util.find_spec("rasa"), "Run with the locked Mantle interpreter for native invocation checks")
class NativeBindings(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        from contextlib import nullcontext, closing
        import sqlite3
        from types import SimpleNamespace
        from unittest.mock import patch
        from rasa.mantle.orchestration.tool_execution.invoker import ToolInvoker
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "sample.sqlite"
        with closing(sqlite3.connect(self.path)) as connection:
            connection.execute("CREATE TABLE Example(value INTEGER)")
            connection.commit()
        self.before = self.path.read_bytes()
        env = patch.dict(os.environ, {"CHINOOK_DATABASE": str(self.path)})
        env.start()
        self.addCleanup(env.stop)
        spec = importlib.util.spec_from_file_location("native_chinook_bindings", PROJECT / "skills/query_store/tools.py")
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        # Controlled tracker: the actual invoker constructs and supplies ToolContext.
        self.session = SimpleNamespace(memory_scope=lambda: ("query_store", "query_store"), recording_write=lambda **kwargs: nullcontext())
        self.invoker = ToolInvoker(mcp_runtime=None, tool_timeout=10, verbatim_trigger_evaluator=None)

    async def asyncTearDown(self):
        self.assertEqual(self.path.read_bytes(), self.before)

    async def invoke(self, function, query):
        import json
        return json.loads(await self.invoker.call_tool_func(function, "sql_db_query", {"query": query}, self.session))

    async def test_actual_invoker_runs_the_query_binding(self):
        result = await self.invoke(self.module.sql_db_query, "SELECT 1 AS one")
        self.assertEqual(result["rows"], [[1]])

    async def test_actual_invoker_preserves_result_contract_refusals(self):
        for query, reason in [
            ("SELECT hex(zeroblob(65536)) AS value LIMIT 1", "sqlite_value_too_large"),
            ("SELECT zeroblob(8) AS value LIMIT 1", "unsupported_result_value"),
            ("SELECT 1e999 AS value", "unsupported_result_value"),
        ]:
            with self.subTest(query=query):
                result = await self.invoke(self.module.sql_db_query, query)
                self.assertEqual((result["status"], result["reason"]), ("error", reason))
                self.assertNotIn("rows", result)

    async def test_actual_invoker_preserves_write_refusal(self):
        result = await self.invoke(self.module.sql_db_query, "DELETE FROM Example")
        self.assertEqual(result["status"], "error")
        from rasa.mantle.orchestration.tool_execution.payload import error_from_tool_payload
        # This application refusal is not a dispatch exception. Inspect both layers.
        self.assertEqual(error_from_tool_payload(result), (False, None))
        from rasa.mantle.orchestration.tool_execution.constraints import ToolConstraintsExecutor
        from types import SimpleNamespace
        import json
        for label, query, expected in [
            ('refused write', 'DELETE FROM Example', False),
            ('valid read', 'SELECT 1 AS one', True),
        ]:
            payload = await self.invoke(self.module.sql_db_query, query)
            events = []
            tracker = SimpleNamespace(memory_scope=lambda: ('query_store', 'query_store'), apply_events=events.extend)
            # Actual deterministic SDK event recorder, with a controlled tracker.
            # This is not a model conversation or the full LLM orchestration path.
            ToolConstraintsExecutor._record_execute_tool_event(tracker, tool_name='sql_db_query', arguments={'query': query}, result=json.dumps(payload))
            event = next(e.as_dict() for e in events if e.type_name == 'tool_executed')
            application = json.loads(event['result'])
            flag_only = not event['is_error']
            both = flag_only and application.get('status') == 'ok'
            self.assertTrue(flag_only)
            self.assertEqual(both, expected)
            print(f"{label} | application={application['status']} | is_error={event['is_error']} | flag-only={flag_only} | both={both}")

    async def test_removing_context_breaks_the_actual_invocation(self):
        from shared import database
        from rasa.mantle.tools.result import ToolResult
        async def broken_query(query: str):
            return ToolResult(llm_response=database.query(query))
        result = await self.invoke(broken_query, "SELECT 1 AS one")
        self.assertIn("unexpected keyword argument 'context'", result["error"])


if __name__ == "__main__":
    unittest.main()
