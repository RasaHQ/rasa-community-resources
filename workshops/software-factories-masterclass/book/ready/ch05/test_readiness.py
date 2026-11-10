"""Fail-closed chapter 5 network isolation and pre-provider controls.

These are offline refusal/copy-layout controls, not a completed builder session
or a real protected good/bad product verdict on Linux.
"""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'factory_engine'))
import factory


class ReadinessControls(unittest.TestCase):
    def profile(self):
        return ROOT / 'factory_engine/environment-a6.json'

    def task(self):
        return ROOT / 'tasks/b-limit-currencies.json'

    def test_runner_without_wrapper_never_judges(self):
        result = subprocess.run([sys.executable, '-B', str(ROOT / 'run_a6.py'), str(self.task()), 'not-an-attempt'],
                                env={'PATH': '/no-sandbox-here', 'PYTHONDONTWRITEBYTECODE': '1'},
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn('proven no-network wrapper', result.stdout)
        self.assertNotIn('REJECT', result.stdout)
        self.assertNotIn('ACCEPT', result.stdout)
        self.assertEqual(result.stderr, '')

    def test_full_factory_without_wrapper_never_prepares_or_tests_candidate(self):
        with tempfile.TemporaryDirectory() as tmp, \
                patch.object(factory, 'load_isolation', return_value=None), \
                patch.object(factory, 'run_tests') as tests, \
                patch.object(factory, 'prepare') as prepare, contextlib.redirect_stdout(io.StringIO()):
            code = factory.main(self.task(), ROOT / 'not-an-attempt', Path(tmp) / 'run',
                                pack_root=ROOT, environment_path=self.profile(), strict=True)
            self.assertFalse((Path(tmp) / 'run').exists())
        self.assertEqual(code, 2)
        prepare.assert_not_called()
        tests.assert_not_called()

    def copy_pins(self, root):
        task = json.loads(self.task().read_text())
        for item in [task['acceptance'], *task['support']]:
            target = root / item['path']
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / item['path'], target)
        (root / 'tasks').mkdir()
        target = root / 'tasks/b-limit-currencies.json'
        target.write_text(json.dumps(task))
        return target

    def test_tampered_helper_is_refused_before_its_code_runs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            task = self.copy_pins(root)
            helper = root / 'acceptance/isolation.py'
            sentinel = root / 'SENTINEL'
            with helper.open('a') as file:
                file.write("\nfrom pathlib import Path as P\nP(" + repr(str(sentinel)) + ").write_text('ran')\n")
            self.assertIsNone(factory.load_isolation(self.profile(), pack_root=root, task_path=task))
            self.assertFalse(sentinel.exists())
            # Positive control: this exact tampered code would create the marker if imported.
            spec = importlib.util.spec_from_file_location('tamper_control', helper)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            self.assertTrue(sentinel.exists())

    def test_missing_helper_pin_is_not_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            task = self.copy_pins(root)
            data = json.loads(task.read_text())
            data['support'] = [item for item in data['support'] if item['path'] != 'acceptance/isolation.py']
            task.write_text(json.dumps(data))
            self.assertTrue(factory.sandbox_unavailable(self.profile(), pack_root=root, task_path=task))

    def test_profile_without_task_context_cannot_claim_isolation(self):
        self.assertTrue(factory.sandbox_unavailable(self.profile()))

    def test_legacy_mac_only_profiles_still_refuse_linux(self):
        with tempfile.TemporaryDirectory() as tmp:
            profile = Path(tmp) / 'profile.json'
            profile.write_text(json.dumps({'requires_sandbox_exec': True}))
            with patch.object(factory.platform, 'system', return_value='Linux'):
                self.assertTrue(factory.sandbox_unavailable(profile))

    def test_pinned_helper_never_proves_an_empty_or_pass_through_wrapper(self):
        module = factory.load_isolation(self.profile(), pack_root=ROOT, task_path=self.task())
        self.assertIsNotNone(module)
        self.assertFalse(module.blocks([]))
        with tempfile.TemporaryDirectory() as tmp:
            wrapper = Path(tmp) / 'pass-through'
            wrapper.write_text('#!/bin/sh\nexec "$@"\n')
            wrapper.chmod(0o700)
            self.assertFalse(module.blocks([str(wrapper)]))

    def test_strict_protected_copy_keeps_helper_next_to_acceptance(self):
        seen = []
        def inspect_copy(path, project, scratch, **kwargs):
            helper = path.parent / 'isolation.py'
            self.assertEqual(helper.read_bytes(), (ROOT / 'acceptance/isolation.py').read_bytes())
            self.assertTrue(kwargs['strict'])
            seen.append(str(path))
            return {'passed': True, 'summary': 'synthetic copy-layout control', 'output': ''}
        with tempfile.TemporaryDirectory() as tmp, \
                patch.object(factory, 'sandbox_unavailable', return_value=False), \
                patch.object(factory, 'prepare', return_value=({'zeocore': '0.35.6'}, [])), \
                patch.object(factory, 'run_tests', side_effect=inspect_copy), \
                contextlib.redirect_stdout(io.StringIO()):
            result = factory.main(self.task(), ROOT / 'candidates/market-good', Path(tmp) / 'run',
                                  pack_root=ROOT, environment_path=self.profile(), strict=True)
        self.assertEqual(result, 0)
        self.assertEqual(len(seen), 1)  # Synthetic layout only; no real product verdict claimed.

    def test_native_driver_refuses_before_prepare_or_provider_dispatch(self):
        driver_path = ROOT / 'factory_engine/agent-runs/drivers/openai_factory_driver.py'
        spec = importlib.util.spec_from_file_location('driver_readiness_control', driver_path)
        driver = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(driver)
        original_module = driver.module
        def select(name):
            return factory if name == 'factory' else original_module(name)
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / 'scratch'
            driver.module('scratch').main(self.task(), workspace, pack_root=ROOT, instructions='AGENTS-a6.md')
            with patch.object(driver, 'module', side_effect=select), \
                    patch.object(factory, 'load_isolation', return_value=None), \
                    patch.object(factory, 'prepare') as prepare, \
                    patch.object(driver, 'native_builder') as provider, \
                    contextlib.redirect_stdout(io.StringIO()):
                result = driver.execute(self.task(), workspace, Path(tmp) / 'run', client=object(),
                                        model='SCRIPTED-no-provider-dispatch',
                                        pack_root=ROOT, environment_path=self.profile(),
                                        expected_cost_cents=[0, 0], mode='SCRIPTED')
            prepare.assert_not_called()
            provider.assert_not_called()
            self.assertEqual(result, 2)
            record = json.loads((Path(tmp) / 'run/console.json').read_text())
            self.assertEqual(record['state'], 'NOT_READY')


if __name__ == '__main__':
    unittest.main()
