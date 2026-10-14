"""Actual verification tool plus native memory manager, with a controlled tracker."""
import importlib.util
import os
import subprocess
import tempfile
from importlib.metadata import version
from pathlib import Path
from types import SimpleNamespace
import sys
import unittest

PROJECT = Path(__file__).resolve().parents[1]
NATIVE = importlib.util.find_spec('rasa') is not None


@unittest.skipUnless(NATIVE, 'Use this project’s locked Rasa interpreter')
class VerificationMemory(unittest.IsolatedAsyncioTestCase):
    def manager(self, seeded_false=False):
        from rasa.mantle.memory.schema import ProjectMemorySchema, SkillMemoryContract
        from rasa.mantle.memory.manager import MemoryManager
        import yaml
        schema = ProjectMemorySchema.from_yaml(PROJECT / 'memory.yml')
        if seeded_false:
            schema = schema.model_copy(update={'fields': {
                **schema.fields,
                'authenticated': schema.fields['authenticated'].model_copy(update={'initial_value': False}),
            }})
        contract = SkillMemoryContract.model_validate(yaml.safe_load(
            (PROJECT / 'skills/authenticate/memory.yml').read_text()))
        skill = SimpleNamespace(memory=contract)
        catalog = SimpleNamespace(skill_by_id=lambda name: skill if name == 'authenticate' else None)
        slots = {'project.' + key: field.initial_value for key, field in schema.fields.items()}
        def apply_events(events):
            for event in events:
                slots[event.key] = event.value
        handle = SimpleNamespace(get_slot=slots.get, apply_events=apply_events)
        manager = MemoryManager(catalog, schema, handle)
        context = SimpleNamespace(memory=SimpleNamespace(
            set=lambda name, value: manager.set('authenticate', 'authenticate', name, value)))
        return manager, context, slots

    async def asyncSetUp(self):
        self.assertEqual(version('rasa-pro'), '3.21.0.dev5')
        sys.path.insert(0, str(PROJECT))
        self.addCleanup(lambda: sys.path.remove(str(PROJECT)))
        spec = importlib.util.spec_from_file_location('sterling_verification', PROJECT / 'skills/authenticate/tools.py')
        self.tools = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.tools)

    async def test_first_verification_writes_identity_and_flag(self):
        manager, context, slots = self.manager()
        result = await self.tools.verify_passphrase('bluebird', context)
        self.assertTrue(result.llm_response['ok'])
        self.assertEqual(slots['project.customer_id'], result.llm_response['customer_id'])
        self.assertIs(slots['project.authenticated'], True)
        self.assertEqual(slots['authenticate.verification_method'], 'passphrase')

    async def test_false_seed_blocks_the_first_flag_update(self):
        from rasa.mantle.memory.manager import ProjectMemoryAlreadySetError
        manager, context, slots = self.manager(seeded_false=True)
        with self.assertRaises(ProjectMemoryAlreadySetError):
            await self.tools.verify_passphrase('bluebird', context)
        self.assertIs(slots['project.authenticated'], False)

    async def test_qualified_first_write_is_allowed_but_overwrite_is_refused(self):
        from rasa.mantle.memory.manager import ProjectMemoryAlreadySetError
        manager, context, slots = self.manager()
        manager.set('authenticate', 'authenticate', 'project.customer_id', 'fixture-customer')
        with self.assertRaises(ProjectMemoryAlreadySetError):
            manager.set('authenticate', 'authenticate', 'project.customer_id', 'different-customer')
        self.assertEqual(slots['project.customer_id'], 'fixture-customer')


@unittest.skipUnless(NATIVE, 'Use this project’s locked Rasa interpreter')
class ColdArchive(unittest.TestCase):
    def test_archive_loads_in_a_fresh_process_without_the_source_path(self):
        from rasa.mantle.model_archive.snapshot import package_model_archive
        with tempfile.TemporaryDirectory() as temp:
            result = package_model_archive(str(PROJECT / 'agent.yml'), temp,
                                           fixed_model_name='sterling-memory', validate=True)
            self.assertEqual(result.code, 0)
            env = {key: value for key, value in os.environ.items()
                   if not key.endswith('_API_KEY') and key not in {'RASA_LICENSE', 'RASA_PRO_LICENSE', 'PYTHONPATH'}}
            env.update(RASA_TELEMETRY_ENABLED='false', LITELLM_LOCAL_MODEL_COST_MAP='True')
            code = "import asyncio, sys; from rasa.core.agent import Agent; from rasa.core.config.configuration import Configuration; Configuration.initialise_endpoints(None); agent=Agent.load(sys.argv[1]); asyncio.run(agent.close()); print('cold archive load: ok')"
            child = subprocess.run([sys.executable, '-B', '-c', code, result.model],
                                   cwd=temp, env=env, capture_output=True, text=True, timeout=90)
            self.assertEqual(child.returncode, 0, child.stderr)
            self.assertIn('cold archive load: ok', child.stdout)


if __name__ == '__main__':
    unittest.main()
