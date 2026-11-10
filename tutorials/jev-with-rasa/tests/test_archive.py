"""A freshly trained archive must load outside the project directory."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


class ColdArchive(unittest.TestCase):
    def test_trained_archive_loads(self):
        models = Path(__file__).resolve().parents[1] / "mantle/models"
        archives = sorted(models.glob("*.tar.gz"), key=lambda p: p.stat().st_mtime)
        if not archives:
            self.skipTest("Run make train first to qualify a cold archive")
        code = ("import asyncio; from rasa.core.agent import Agent; "
                "from rasa.core.config.configuration import Configuration; "
                "Configuration.initialise_endpoints(None); "
                "a=Agent.load(__import__('sys').argv[1]); asyncio.run(a.close()); "
                "print('cold archive load: ok')")
        env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run([sys.executable, "-B", "-c", code, str(archives[-1])],
                                    cwd=directory, env=env, capture_output=True, text=True, timeout=90)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("cold archive load: ok", result.stdout)
