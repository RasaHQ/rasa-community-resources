"""Drive the real CLI handoff and hosted builder using explicit synthetic artifacts."""

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch
from contextlib import nullcontext, redirect_stdout
import asyncio
import importlib.util
import io
from factory import build


class Handoff(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.raw = (build.ROOT / "reference/full.json").read_bytes()

    def hosted(self, path):
        c = MagicMock()
        s = c.beta.agents.sessions
        stream = MagicMock()
        stream.get_final_result.return_value = SimpleNamespace(
            session_id="simulated-id"
        )
        s.create.return_value.with_result_collection.return_value = nullcontext(stream)
        s.artifacts.list.return_value = [SimpleNamespace(path=path, id="artifact-1")]
        content = MagicMock()
        content.stream_to_file.side_effect = lambda dst: dst.write_bytes(self.raw)
        s.artifacts.with_streaming_response.content.return_value = nullcontext(content)
        with (
            patch.object(build, "ROOT", self.root),
            patch.dict(sys.modules, openai=SimpleNamespace(OpenAI=lambda **kwargs: c)),
        ):
            run = build.propose("hosted", "test")
        s.artifacts.list.assert_called_once_with("simulated-id")
        return run

    def test_download_receipt(self):
        run = self.hosted("/workspace/outputs/agent.json")
        r = json.loads((run / "receipt.json").read_text())
        self.assertEqual(r["sha256"], hashlib.sha256(self.raw).hexdigest())
        self.assertEqual(r["session"], "simulated-id")

    def test_oversized_instructions_are_reported_as_a_rejected_candidate(self):
        spec = json.loads(self.raw)
        spec["instructions"] = "Say the times. " * 500
        self.assertGreater(len(spec["instructions"]), 2500)
        self.raw = json.dumps(spec).encode()
        with self.assertRaises(SystemExit) as stop:
            self.hosted("/workspace/outputs/agent.json")
        self.assertEqual(stop.exception.code, 3)
        receipt = json.loads(next(self.root.glob("runs/*/receipt.json")).read_text())
        self.assertEqual(receipt["outcome"], "invalid_candidate")
        self.assertEqual(receipt["reason"], f"Invalid instructions: {len(spec['instructions'])} characters, allowed 10 to 2500")
        self.assertEqual(receipt["session"], "simulated-id")

    def test_task_states_the_limits_the_compiler_enforces(self):
        self.assertIn("2000 characters", build.TASK)
        self.assertIn("2500", build.TASK)

    def test_studio_tool_names_the_rejected_state(self):
        source = (build.ROOT / "studio/skills/build_agent/tools.py").read_text()
        self.assertIn("returncode == 3", source)
        self.assertIn("nothing was built", source)

    def spoken_line(self, raw=None):
        if raw is not None:
            self.raw = raw
        out = io.StringIO()
        code = 0
        with redirect_stdout(out):
            try:
                self.hosted("/workspace/outputs/agent.json")
            except SystemExit as stop:
                code = stop.code
        lines = [l for l in out.getvalue().splitlines() if l.startswith("Spoken: ")]
        self.assertEqual(len(lines), 1, out.getvalue())
        return code, lines[0][len("Spoken: "):], out.getvalue()

    def assertListenable(self, spoken, full):
        self.assertLess(len(spoken), 200)
        self.assertNotIn("simulated-id", spoken)
        self.assertNotIn("/", spoken)
        self.assertNotRegex(spoken, r"[0-9a-f]{32}")
        self.assertIn("simulated-id", full)  # the ids stay in the record

    def test_ready_candidate_speaks_its_own_counts_without_ids(self):
        spec = json.loads(self.raw)
        code, spoken, full = self.spoken_line()
        self.assertEqual(code, 0)
        self.assertListenable(spoken, full)
        self.assertIn("accepted", spoken)
        self.assertIn("%d tools" % len(spec["tools"]), spoken)
        self.assertIn("%d characters" % len(spec["instructions"]), spoken)

    def test_rejected_candidate_speaks_the_reason_without_ids(self):
        spec = json.loads(self.raw)
        spec["instructions"] = "Say the times. " * 500
        code, spoken, full = self.spoken_line(json.dumps(spec).encode())
        self.assertEqual(code, 3)
        self.assertListenable(spoken, full)
        self.assertIn("rejected", spoken)
        self.assertIn("Invalid instructions: %d characters" % len(spec["instructions"]), spoken)
        self.assertIn("Nothing was built", spoken)
        self.assertNotIn("accepted", spoken)

    def studio_tool(self, returncode, stdout):
        names = ["rasa", "rasa.mantle", "rasa.mantle.tools", "rasa.mantle.tools.decorator", "rasa.mantle.tools.result"]
        stubs = {n: MagicMock() for n in names}
        stubs["rasa.mantle.tools.decorator"].tool = lambda **kw: (lambda f: f)
        stubs["rasa.mantle.tools.result"].ToolResult = lambda llm_response: llm_response
        spec = importlib.util.spec_from_file_location("studio_tools_probe", build.ROOT / "studio/skills/build_agent/tools.py")
        module = importlib.util.module_from_spec(spec)
        proc = MagicMock(returncode=returncode)
        async def communicate():
            return stdout.encode(), b""
        proc.communicate = communicate
        async def spawn(*args, **kwargs):
            return proc
        with patch.dict(sys.modules, stubs), patch.dict(os.environ, {"TRAVEL_FACTORY_ROOT": str(build.ROOT)}):
            spec.loader.exec_module(module)
            with patch.object(module.asyncio, "create_subprocess_exec", spawn):
                return asyncio.run(module.propose_travel_agent(None, "brief"))

    def test_studio_tool_returns_spoken_and_record_separately(self):
        full = '{"session": "sess_abc"}\nReview: /x/agent.json\nSpoken: The compiler accepted the candidate: 4 tools.\n'
        result = self.studio_tool(0, full)
        self.assertEqual(result["spoken"], "The compiler accepted the candidate: 4 tools.")
        self.assertIn("sess_abc", result["record"])
        self.assertNotIn("sess_abc", result["spoken"])

    def test_studio_tool_never_invents_success(self):
        for code, out in ((0, "no spoken line here"), (1, "Spoken: stale"), (2, "")):
            result = self.studio_tool(code, out)
            self.assertIn("uncertain", result["spoken"])
            self.assertNotIn("accepted", result["spoken"])

    def test_wrong_path_keeps_session(self):
        with self.assertRaises(ValueError):
            self.hosted("/workspace/outputs/notes.txt")
        self.assertEqual(
            next(self.root.glob("runs/*/session.txt")).read_text(), "simulated-id"
        )
        self.assertFalse(list(self.root.glob("runs/*/receipt.json")))

    def test_modified_candidate_blocks_build(self):
        run = self.hosted("/workspace/outputs/agent.json")
        with (run / "agent.json").open("ab") as f:
            f.write(b"\n")
        with (
            patch.object(
                sys, "argv", ["build", "approve", str(run), str(self.root / "project")]
            ),
            self.assertRaisesRegex(ValueError, "changed"),
        ):
            build.main()
        self.assertFalse((self.root / "project").exists())
