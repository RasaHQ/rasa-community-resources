"""Tests for what the customer sees after a build. No key, no network, no Mantle: stand-ins replace the rasa imports."""
import asyncio
import sys
import types
import unittest
from pathlib import Path

for name in ("rasa", "rasa.mantle", "rasa.mantle.tools"):
    sys.modules.setdefault(name, types.ModuleType(name))
decorator = types.ModuleType("rasa.mantle.tools.decorator")
decorator.ToolContext = object
decorator.tool = lambda **kwargs: (lambda function: function)
result_module = types.ModuleType("rasa.mantle.tools.result")


class ToolResult:
    def __init__(self, llm_response=None):
        self.llm_response = llm_response


result_module.ToolResult = ToolResult
sys.modules["rasa.mantle.tools.decorator"] = decorator
sys.modules["rasa.mantle.tools.result"] = result_module
sys.path.insert(0, str(Path(__file__).resolve().parent))

import tools  # noqa: E402

DONE = {"build_id": "b-123", "saved": True, "file": "scratch/build-b-123/check_line_status.py", "sha256": "ab" * 32,
        "builder_said": "I wrote the check."}


class Context:
    def __init__(self):
        self.sent = []

    async def send(self, text):
        self.sent.append(text)


class Show(unittest.TestCase):
    def test_fixture_keeps_its_label_in_the_customer_message(self):
        text = tools.describe({**DONE, "mode": "fixture"})
        self.assertTrue(text.startswith("Fixture build "))
        self.assertIn("No Agents session was started.", text)
        self.assertIn(DONE["sha256"], text)

    def test_saved_build_shows_id_path_and_hash_exactly(self):
        text = tools.describe(DONE)
        for value in ("b-123", "scratch/build-b-123/check_line_status.py", "ab" * 32):
            self.assertIn(value, text)

    def test_unsaved_build_says_so(self):
        self.assertIn("reported no saved file", tools.describe({"build_id": "b-9", "saved": False}))

    def test_only_the_busy_refusal_says_no_build_started(self):
        busy = {"started": False, "saved": False, "builder_said": "A build is already running."}
        self.assertTrue(tools.describe(busy).startswith("No build started."))
        for unknown in ({}, {"saved": False}, {"builder_said": "odd"}):
            text = tools.describe(unknown)
            self.assertNotIn("No build started", text)
            self.assertIn("cannot tell whether a build started", text)

    def test_malformed_fields_are_unknown_or_refused(self):
        good = dict(DONE)
        for bad in ({**good, "saved": "true"}, {**good, "saved": 1}, {**good, "build_id": ["bad"]}, {**good, "build_id": ""}):
            self.assertIn("cannot tell whether a build started", tools.describe(bad))
            self.assertNotIn("saved a file", tools.describe(bad))
        for bad in ({k: v for k, v in good.items() if k != "sha256"}, {**good, "sha256": "ab"}, {**good, "sha256": "AB" * 32},
                    {**good, "file": ""}, {k: v for k, v in good.items() if k != "file"}):
            text = tools.describe(bad)
            self.assertIn("Do not use it", text)
            self.assertNotIn("saved a file.", text)
        self.assertIn("cannot tell", tools.describe([1]))

    def test_saved_false_does_not_claim_the_build_ended(self):
        text = tools.describe({"build_id": "b-9", "saved": False, "builder_said": "x"})
        self.assertIn("saved=false", text)
        self.assertNotIn("ended without", text)
        self.assertIn("cannot confirm", text)

    def test_error_result_and_non_dict_are_unknown(self):
        self.assertEqual(tools.parse(types.SimpleNamespace(isError=True, structuredContent=DONE, content=[])), {})
        self.assertEqual(tools.parse(types.SimpleNamespace(structuredContent=None, content=[types.SimpleNamespace(text="[1]")])), {})

    def test_malformed_text_and_timeout_are_unknown_and_not_retried(self):
        for failure in (ValueError("bad json"), TimeoutError()):
            calls = []

            async def fail(request, failure=failure):
                calls.append(request)
                raise failure
            tools._call_server = fail
            context = Context()
            asyncio.run(tools.build_change("x", context=context))
            self.assertEqual(len(calls), 1)
            self.assertIn("cannot tell whether a build started", context.sent[0])
            self.assertNotIn("No build started", context.sent[0])

    def test_parse_reads_structured_then_text(self):
        structured = types.SimpleNamespace(structuredContent=DONE, content=[])
        text = types.SimpleNamespace(structuredContent=None, content=[types.SimpleNamespace(text='{"build_id": "b-1", "saved": false}')])
        self.assertEqual(tools.parse(structured)["build_id"], "b-123")
        self.assertEqual(tools.parse(text)["build_id"], "b-1")

    def test_tool_sends_the_message_to_the_customer(self):
        async def fake(request):
            return types.SimpleNamespace(structuredContent=DONE, content=[])
        tools._call_server = fake
        context = Context()
        outcome = asyncio.run(tools.build_change("add a line status check", context=context))
        self.assertEqual(context.sent, [tools.describe(DONE)])
        self.assertEqual(outcome.llm_response["shown_to_customer"], context.sent[0])

    def test_unreachable_server_is_shown_not_raised(self):
        async def broken(request):
            raise ConnectionRefusedError()
        tools._call_server = broken
        context = Context()
        asyncio.run(tools.build_change("x", context=context))
        self.assertIn("cannot tell whether a build started", context.sent[0])


if __name__ == "__main__":
    unittest.main()
