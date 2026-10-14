"""Package both variants and check loaded native constraints in fresh processes.

This is archive/runtime bootstrap qualification, not an orchestrated chat or a
measurement of model interpretation of external content or caller consent.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from prepare import prepare

COLD_PROBE = """
import asyncio, json, sys
from rasa.core.agent import Agent
from rasa.core.config.configuration import Configuration
from rasa.mantle.skills.conditions import is_confirmation_gate_active
Configuration.initialise_endpoints(None)
agent = Agent.load(sys.argv[1])
try:
    catalog = agent.processor.mantle_static_data.skill_catalog
    skill = catalog.skill_by_id('review_case')
    gate = catalog.effective_tool_gate('review_case', '', 'record_local_canary')
    assert gate is not None
    print('ARCHIVE_CHECK=' + json.dumps({
        'confirmation_enabled': is_confirmation_gate_active(gate.requires_confirmation),
        'imports': sorted(skill.import_tool_names),
    }))
finally:
    asyncio.run(agent.close())
"""


class ColdArchives(unittest.TestCase):
    def test_both_archives_load_without_source_path_and_keep_their_constraint(self):
        from rasa.mantle.model_archive.snapshot import package_model_archive
        fake = {'OPENAI_API_KEY': 'placeholder-not-a-real-key',
                'RASA_LICENSE': '', 'RASA_PRO_LICENSE': '',
                'RASA_TELEMETRY_ENABLED': 'false', 'DO_NOT_TRACK': '1',
                'LITELLM_LOCAL_MODEL_COST_MAP': 'True',
                'LLM_API_HEALTH_CHECK': 'false', 'PYTHON_DOTENV_DISABLED': 'true'}
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, fake):
            root = Path(temp)
            observed = []
            for variant in ('gated', 'ungated'):
                source = root / variant
                prepare(variant, source, 8937, scripted_model_port=8938)
                result = package_model_archive(str(source / 'agent.yml'),
                    str(root / 'archives'), fixed_model_name=variant, validate=True)
                self.assertEqual(result.code, 0)
                archive = Path(result.model)
                digest = hashlib.sha256(archive.read_bytes()).hexdigest()
                source.rename(root / f'.retained-{variant}')
                self.assertFalse(source.exists())
                cold_dir = root / f'cold-{variant}'
                cold_dir.mkdir()
                # The subprocess starts outside the supplied source project and
                # receives no real credentials or parent import path.
                env = {key: value for key, value in os.environ.items()
                       if not key.endswith(('_API_KEY', '_TOKEN', '_SECRET', '_PASSWORD'))
                       and key not in {'RASA_LICENSE', 'RASA_PRO_LICENSE', 'PYTHONPATH'}}
                env.update({key: value for key, value in fake.items()
                            if key not in {'OPENAI_API_KEY', 'RASA_LICENSE', 'RASA_PRO_LICENSE'}})
                child = subprocess.run([sys.executable, '-B', '-c', COLD_PROBE, str(archive)],
                    cwd=cold_dir, env=env, capture_output=True, text=True, timeout=90)
                self.assertEqual(child.returncode, 0, child.stderr)
                checks = [line.removeprefix('ARCHIVE_CHECK=') for line in child.stdout.splitlines()
                          if line.startswith('ARCHIVE_CHECK=')]
                self.assertEqual(len(checks), 1)
                record = json.loads(checks[0])
                self.assertEqual(record['confirmation_enabled'], variant == 'gated')
                self.assertEqual(record['imports'], ['mcp/fictional_support:read_case'])
                observed.append(record)
                print(f'Archive {variant} sha256={digest}; cold bootstrap passed')
            self.assertEqual(observed[0]['imports'], observed[1]['imports'])


if __name__ == '__main__':
    unittest.main()
