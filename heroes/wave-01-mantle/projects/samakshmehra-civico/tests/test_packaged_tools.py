"""Load actual skill tools outside the source tree on the frozen Rasa SDK.

This checks native loading and direct tool calls, not a model conversation.
No training, provider request, licence or existing mutable database is used.
"""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

SOURCE = Path(__file__).resolve().parents[1]


class TestPackagedTools(unittest.TestCase):
    def test_second_complaint_after_snapshot_import_path_is_removed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            snapshot = root / "snapshot"
            assets = root / "assets"
            cold = root / "cold"
            cold.mkdir()
            for folder in ("lib", "tools", "skills/check_status", "skills/report_problem"):
                shutil.copytree(SOURCE / folder, snapshot / folder,
                                ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
            (assets / "data").mkdir(parents=True)
            for path in (SOURCE / "data").glob("*.json"):
                shutil.copyfile(path, assets / "data" / path.name)
            child = r'''
import asyncio, json, shutil, sys
from pathlib import Path
from rasa.mantle.tools.loader import _load_tool_module
snapshot = Path(sys.argv[1])
functions = _load_tool_module(snapshot / 'skills/check_status/tools.py',
                              'civico_packaged_status_regression', snapshot)
assert str(snapshot) not in sys.path
# An editable project install can otherwise rescue the source-only namespace.
# Packaged tools must work without resolving a skill module from that install.
for name in list(sys.modules):
    if name == 'skills' or name.startswith('skills.'):
        del sys.modules[name]
class NoSourceSkills:
    def find_spec(self, fullname, path=None, target=None):
        if fullname == 'skills' or fullname.startswith('skills.'):
            raise ModuleNotFoundError("No module named 'skills'")
sys.meta_path.insert(0, NoSourceSkills())
assert all(Path(func.__code__.co_filename).is_relative_to(snapshot)
           for func in functions.values())
# Agent.load removes its extracted source directory after loading tools too.
shutil.rmtree(snapshot)
class Memory:
    def __init__(self): self.values = {}
    def get(self, name, default=None): return self.values.get(name, default)
    def set(self, name, value): self.values[name] = value
class Context:
    def __init__(self): self.memory = Memory(); self.said = []
    async def send(self, text): self.said.append(text)
async def check():
    context = Context()
    listed = (await functions['list_my_complaints']('0000000501', context)).llm_response
    assert listed['found'] >= 2, listed
    selected = (await functions['choose_complaint']('second', context)).llm_response
    assert selected['complaint_id'] == listed['options'][1]['complaint_id'], selected
    assert context.said
    print('COLD_SELECTION_OK')
asyncio.run(check())
'''
            env = {key: value for key, value in os.environ.items()
                   if not key.startswith("PYTHON") and not any(
                       word in key.upper() for word in
                       ("KEY", "TOKEN", "SECRET", "PASSWORD", "CREDENTIAL", "LICENSE"))}
            env.update(CIVICO_PROJECT_ROOT=str(assets),
                       CIVICO_DB_PATH=str(assets / "test.db"),
                       PYTHONDONTWRITEBYTECODE="1", PYTHON_DOTENV_DISABLED="true",
                       RASA_TELEMETRY_ENABLED="false", LLM_API_HEALTH_CHECK="false",
                       LITELLM_LOCAL_MODEL_COST_MAP="True", DO_NOT_TRACK="1",
                       OPENAI_API_KEY="placeholder-not-a-real-key")
            result = subprocess.run([sys.executable, "-c", child, str(snapshot)],
                                    cwd=cold, env=env, capture_output=True,
                                    text=True, timeout=90)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("COLD_SELECTION_OK", result.stdout)


if __name__ == "__main__":
    unittest.main()
