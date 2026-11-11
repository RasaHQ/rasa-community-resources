"""Both shipped tool copies: real pinned SDK, in-memory context, no network."""
import asyncio
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[1]


def load_tool(skill):
    spec = importlib.util.spec_from_file_location(skill + "_tools", ROOT / "skills" / skill / "tools.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.suggest_support_plan


class Memory:
    def __init__(self, values):
        self.values = dict(values)

    def get(self, key):
        return self.values.get(key)

    def set(self, key, value):
        self.values[key] = value


class SupportToolTests(unittest.TestCase):
    def test_missing_context_refuses_both_tool_copies(self):
        for skill in ("speech_support", "view_transactions"):
            with self.subTest(skill=skill):
                response = asyncio.run(load_tool(skill)()).llm_response
                self.assertFalse(response["ok"])
                self.assertEqual(response["error"], "no_context")

    def test_focus_and_age_are_isolated_to_each_context(self):
        for skill in ("speech_support", "view_transactions"):
            with self.subTest(skill=skill):
                tool = load_tool(skill)
                first = SimpleNamespace(memory=Memory({"child_age": "8", "focus_area": "stammering"}))
                second = SimpleNamespace(memory=Memory({"child_age": "12", "focus_area": "confidence"}))
                a = asyncio.run(tool(context=first)).llm_response
                b = asyncio.run(tool(context=second)).llm_response
                self.assertEqual((a["child_age"], b["child_age"]), ("8", "12"))
                self.assertIn("breaths", a["exercise"])
                self.assertIn("finger", b["exercise"])
                self.assertEqual(first.memory.get("support_focus"), "stammering")
                self.assertEqual(second.memory.get("support_focus"), "confidence")

    def test_unspecified_fields_use_declared_defaults(self):
        for skill in ("speech_support", "view_transactions"):
            with self.subTest(skill=skill):
                context = SimpleNamespace(memory=Memory({}))
                response = asyncio.run(load_tool(skill)(context=context)).llm_response
                self.assertTrue(response["ok"])
                self.assertEqual(response["child_age"], "not specified")
                self.assertEqual(response["focus_area"], "general confidence")
                self.assertEqual(len(response["suggestions"]), 3)


if __name__ == "__main__":
    unittest.main()
