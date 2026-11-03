"""Mantle passes a `context` argument to every tool call; a tool without that parameter fails at run time."""
import ast
from pathlib import Path
from tempfile import TemporaryDirectory
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from factory.build import generate


def tool_functions(source):
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.AsyncFunctionDef) and any(
            getattr(d, "func", d).id == "tool" for d in node.decorator_list if hasattr(getattr(d, "func", d), "id")
        ):
            yield node


def assert_accepts_context(test, source, label):
    names = list(tool_functions(source))
    test.assertTrue(names, label + ": no tools found")
    for node in names:
        args = {a.arg: a for a in node.args.args}
        test.assertIn("context", args, label + ": " + node.name + " lacks a context parameter")
        test.assertEqual(ast.unparse(args["context"].annotation), "ToolContext", node.name)


class ToolContextTests(unittest.TestCase):
    def test_reference_agent_tools_accept_context(self):
        assert_accepts_context(self, (ROOT / "reference/finished-agent/skills/travel_briefing/tools.py").read_text(), "reference")

    def test_studio_tool_accepts_context(self):
        assert_accepts_context(self, (ROOT / "studio/skills/build_agent/tools.py").read_text(), "studio")

    def test_compiled_tools_accept_context(self):
        for spec in ("starter", "full"):
            with TemporaryDirectory() as directory:
                project = Path(directory) / spec
                generate((ROOT / "reference" / (spec + ".json")).read_bytes(), project)
                assert_accepts_context(self, (project / "skills/travel_briefing/tools.py").read_text(), spec)


if __name__ == "__main__":
    unittest.main()
