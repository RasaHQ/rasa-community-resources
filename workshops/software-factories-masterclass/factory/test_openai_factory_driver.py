"""Injected native-boundary and actual filesystem confinement controls.
sow: software-factories-masterclass-SOW-02
"""
import importlib.util
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('openai_factory_driver', HERE / 'agent-runs/drivers/openai_factory_driver.py')
driver = importlib.util.module_from_spec(spec)
spec.loader.exec_module(driver)


class DriverControls(unittest.TestCase):
    def setUp(self):
        cache = HERE / '.driver-test-cache'
        cache.mkdir(exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(dir=cache)
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.workspace = self.root / 'scratch'
        self.workspace.mkdir()
        self.task = {'id': 'A6-fixture', 'request': 'Add a labelled market card.',
                     'allowed_paths': ['product/market.py', 'product/tests/'],
                     'excluded': 'Do not read or edit protected gates.',
                     'acceptance': {'path': 'acceptance/hidden.py', 'sha256': 'hidden-suite-fingerprint'}}
        (self.workspace / 'product').mkdir()
        (self.workspace / 'product' / 'agent.yml').write_text('agent: {}\n')
        (self.workspace / 'tasks').mkdir()
        visible = {key: self.task[key] for key in ('id', 'request', 'allowed_paths', 'excluded')}
        (self.workspace / 'tasks' / 'A6-fixture.json').write_text(json.dumps(visible))
        (self.workspace / 'AGENTS.md').write_text('Only allowed product paths. No protected suite.')
        (self.workspace / '.scratch.json').write_text('{}')
        self.task_path = self.root / 'A6-fixture.json'
        self.task_path.write_text(json.dumps(self.task))
        self.outside = self.root / 'protected.py'
        self.outside.write_text('holdout-must-never-be-visible')

    def files(self):
        result = driver.ConfinedFiles(self.workspace, self.task)
        self.addCleanup(result.close)
        return result

    def test_allowed_read_write_and_visible_task_without_holdout(self):
        files = self.files()
        self.assertTrue(files.read_file({'path': 'AGENTS.md'})['ok'])
        self.assertTrue(files.write_file({'path': 'product/market.py', 'text': 'daily_reference = True\n'})['ok'])
        self.assertEqual((self.workspace / 'product/market.py').read_text(), 'daily_reference = True\n')
        listing = files.list_files({})['files']
        self.assertNotIn('.scratch.json', listing)
        self.assertNotIn('protected.py', listing)
        visible = files.read_file({'path': 'tasks/A6-fixture.json'})['text']
        self.assertNotIn('hidden-suite-fingerprint', visible)

    def test_traversal_prefix_confusion_protected_paths_and_dotfiles_refused(self):
        files = self.files()
        for name in ('../protected.py', str(self.outside), 'product/../protected.py',
                     'product/.env', 'acceptance/hidden.py', 'product/protected/hidden.py',
                     'product/market.py.evil', 'product/tests-not-allowed/fake.py'):
            with self.subTest(path=name):
                self.assertFalse(files.write_file({'path': name, 'text': 'no'})['ok'])
        for name in ('../protected.py', str(self.outside), '.scratch.json', 'acceptance/hidden.py', 'product/.env'):
            self.assertFalse(files.read_file({'path': name})['ok'])
        self.assertEqual(self.outside.read_text(), 'holdout-must-never-be-visible')

    def test_links_fifo_directories_and_hardlinks_do_not_escape_or_block(self):
        files = self.files()
        path = self.workspace / 'product/market.py'
        path.symlink_to(self.outside)
        self.assertFalse(files.read_file({'path': 'product/market.py'})['ok'])
        self.assertFalse(files.write_file({'path': 'product/market.py', 'text': 'no'})['ok'])
        path.unlink()
        os.link(self.outside, path)
        self.assertFalse(files.read_file({'path': 'product/market.py'})['ok'])
        self.assertFalse(files.write_file({'path': 'product/market.py', 'text': 'no'})['ok'])
        path.unlink()
        os.mkfifo(path)
        self.assertFalse(files.read_file({'path': 'product/market.py'})['ok'])
        self.assertFalse(files.write_file({'path': 'product/market.py', 'text': 'no'})['ok'])
        path.unlink()
        directory = self.workspace / 'product/tests'
        directory.symlink_to(self.root)
        self.assertFalse(files.write_file({'path': 'product/tests/protected.py', 'text': 'no'})['ok'])
        self.assertEqual(self.outside.read_text(), 'holdout-must-never-be-visible')

    def test_file_and_cumulative_limits_and_host_credentials(self):
        files = self.files()
        self.assertFalse(files.write_file({'path': 'product/market.py', 'text': 'x' * 65537})['ok'])
        synthetic = 'native-builder-fixture-secret-123456789'
        with patch.dict(os.environ, {'OPENAI_API_KEY': synthetic}):
            self.assertFalse(files.write_file({'path': 'product/market.py', 'text': synthetic})['ok'])
        for _ in range(8):
            self.assertTrue(files.write_file({'path': 'product/market.py', 'text': 'x' * 65536})['ok'])
        self.assertFalse(files.write_file({'path': 'product/market.py', 'text': 'x'})['ok'])

    def test_closed_tools_refuse_all_late_callbacks(self):
        files = self.files()
        files.close()
        self.assertFalse(files.read_file({'path': 'AGENTS.md'})['ok'])
        self.assertFalse(files.write_file({'path': 'product/market.py', 'text': 'late mutation'})['ok'])
        self.assertFalse(files.list_files({})['ok'])
        self.assertFalse((self.workspace / 'product/market.py').exists())

    def test_scratch_preflight_rejects_repo_protected_and_unsafe_task(self):
        driver.validate_scratch(self.workspace, self.task)
        (self.workspace / 'acceptance').mkdir()
        with self.assertRaises(ValueError):
            driver.validate_scratch(self.workspace, self.task)
        (self.workspace / 'acceptance').rmdir()
        unsafe = {**self.task, 'allowed_paths': ['../acceptance/']}
        with self.assertRaises(ValueError):
            driver.ConfinedFiles(self.workspace, unsafe)
        (self.workspace / '.scratch.json').unlink()
        with self.assertRaises(ValueError):
            driver.validate_scratch(self.workspace, self.task)

    def test_one_bounded_native_session_exposes_only_three_file_tools(self):
        calls = []
        events = []
        def invoke(client, **kwargs):
            calls.append(kwargs)
            self.assertEqual(set(kwargs['handlers']), {'list_files', 'read_file', 'write_file'})
            self.assertNotIn('acceptance', json.loads(kwargs['text']))
            self.assertNotIn('hidden-suite-fingerprint', kwargs['text'])
            self.assertTrue(kwargs['handlers']['write_file']({'path': 'product/market.py', 'text': 'REFERENCE = True\n'})['ok'])
            return SimpleNamespace(ok=True)
        result = driver.native_builder(object(), task=self.task, workspace=self.workspace,
                                       event=lambda **values: events.append(values), model='injected-no-network',
                                       invoke=invoke, tool_factory=lambda name, description, schema: {'name': name, 'parameters': schema})
        self.assertTrue(result.ok)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]['max_calls'], 30)
        self.assertNotIn('spend_limit_cents', calls[0])
        self.assertNotIn('spend_control', calls[0])
        self.assertEqual(calls[0]['deadline_seconds'], 120)
        self.assertEqual(calls[0]['environment'], {'type': 'none'})
        self.assertEqual([e['action'] for e in events], ['session_started', 'write_file', 'session_finished'])
        self.assertNotIn('REFERENCE = True', json.dumps(events))

    def test_local_estimate_is_checked_without_sending_any_provider_cap(self):
        calls = []
        def invoke(client, **kwargs):
            calls.append(kwargs)
            return SimpleNamespace(ok=True)
        options = dict(client=object(), task=self.task, workspace=self.workspace,
                       event=lambda **values: None, model='scripted', invoke=invoke,
                       tool_factory=lambda *args: {})
        for limit, estimate in ((None, 1), (200, None), (29, 1), (True, 1), (200, False)):
            with self.subTest(limit=limit, estimate=estimate), self.assertRaises(ValueError):
                driver.native_builder(**options, spend_limit_cents=limit, estimated_cents_per_call=estimate)
        self.assertEqual(calls, [])
        driver.native_builder(**options, spend_limit_cents=30, estimated_cents_per_call=1)
        driver.native_builder(**options)
        self.assertEqual(len(calls), 2)
        for call in calls:
            self.assertNotIn('spend_limit_cents', call)
            self.assertNotIn('spend_control', call)

    def test_native_prompt_exposes_public_limit_without_verifier_metadata(self):
        task = {**self.task, 'limit': 2}
        def invoke(client, **kwargs):
            visible = json.loads(kwargs['text'])
            self.assertEqual(visible['limit'], 2)
            self.assertNotIn('acceptance', visible)
            return SimpleNamespace(ok=True)
        driver.native_builder(object(), task=task, workspace=self.workspace,
                              event=lambda **values: None, model='scripted', invoke=invoke,
                              tool_factory=lambda *args: {})

    def test_noncompleted_session_never_collects_or_accepts_partial_edits(self):
        for status in ('incomplete', 'failed', 'cancelled', None):
            with self.subTest(status=status):
                run = self.root / ('stopped-' + str(status))
                factory = SimpleNamespace(prepare=lambda path: ('injected', []))
                with patch.object(driver, 'module', return_value=factory) as load, \
                        patch.object(driver, 'native_builder', return_value=SimpleNamespace(ok=False, status=status)):
                    code = driver.execute(self.task_path, self.workspace, run, client=object(), model='injected')
                self.assertEqual(code, 2)
                self.assertEqual(load.call_count, 1)  # environment preflight only
                self.assertEqual(json.loads((run / 'console.json').read_text())['state'], 'BUILDER_INCOMPLETE')
                self.assertFalse((run / 'candidate').exists())
                self.assertFalse((run / 'verification').exists())

    def test_host_reuses_collect_factory_and_preserves_each_exit_code(self):
        for code in range(5):
            run = self.root / ('run-' + str(code))
            called = []
            def collect(workspace, candidate, review, **kwargs):
                called.append(('collect', Path(workspace)))
                Path(candidate).mkdir()
                Path(review).mkdir()
                return 0
            def factory(task, candidate, verification, **kwargs):
                called.append(('factory', Path(task)))
                Path(verification).mkdir()
                (Path(verification) / 'decision.json').write_text(json.dumps({'decision': 'ACCEPT' if code == 0 else 'REJECT'}))
                return code
            modules = {'collect': SimpleNamespace(main=collect), 'factory': SimpleNamespace(main=factory, prepare=lambda path: ('injected', []))}
            with patch.object(driver, 'module', side_effect=lambda name: modules[name]), \
                    patch.object(driver, 'native_builder', return_value=SimpleNamespace(ok=True, status='completed')):
                result = driver.execute(self.task_path, self.workspace, run, client=object(), model='injected')
            self.assertEqual(result, code)
            self.assertEqual([name for name, _ in called], ['collect', 'factory'])
            self.assertTrue((run / 'console.json').is_file())
            self.assertFalse((run / 'integration.json').exists())  # integration stays owner-controlled
        with self.assertRaises(ValueError):
            driver.execute(self.task_path, self.workspace, self.workspace / 'evidence', client=object(), model='injected')


if __name__ == '__main__':
    unittest.main()
