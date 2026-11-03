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
from contextlib import nullcontext
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
        self.assertEqual(receipt["reason"], "Invalid instructions")
        self.assertEqual(receipt["session"], "simulated-id")

    def test_task_states_the_limits_the_compiler_enforces(self):
        self.assertIn("2000 characters", build.TASK)
        self.assertIn("2500", build.TASK)

    def test_studio_tool_names_the_rejected_state(self):
        source = (build.ROOT / "studio/skills/build_agent/tools.py").read_text()
        self.assertIn("returncode == 3", source)
        self.assertIn("nothing was built", source)

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
