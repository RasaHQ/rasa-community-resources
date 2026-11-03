"""Validate the completed reference and bind a trained archive to its authored skills.

Run after `uv run rasa train`. These tests do not contact a model or a router.
"""
import asyncio
import importlib.util
from pathlib import Path
import tarfile
import unittest

from rasa.mantle.validation import validate_project

HERE = Path(__file__).resolve().parent


class NativeReference(unittest.TestCase):
    def test_project_is_valid_and_the_simulated_tool_returns_only_reboot(self):
        validate_project(HERE)
        spec = importlib.util.spec_from_file_location("router_tools", HERE / "skills/router_restart/tools.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        result = asyncio.run(module.restart_router())
        self.assertEqual(result.llm_response, {"status": "sent", "command_sent": "REBOOT"})

    def test_trained_archive_keeps_the_exact_skill_and_response_files(self):
        models = list((HERE / "models").glob("*.tar.gz"))
        self.assertTrue(models, "Run uv run rasa train before the native archive test")
        model = max(models, key=lambda path: path.stat().st_mtime)
        sources = list((HERE / "skills").rglob("*.md")) + list((HERE / "skills").rglob("*.yml")) + list((HERE / "skills").rglob("*.py"))
        sources.append(HERE / "responses.yml")
        with tarfile.open(model) as archive:
            for source in sources:
                member = "mantle_snapshot/" + str(source.relative_to(HERE))
                handle = archive.extractfile(member)
                self.assertIsNotNone(handle, member)
                self.assertEqual(handle.read(), source.read_bytes(), member)


if __name__ == "__main__":
    unittest.main()
