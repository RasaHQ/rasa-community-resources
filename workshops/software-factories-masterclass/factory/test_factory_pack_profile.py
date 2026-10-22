"""Existing factory pack-root and strict verifier compatibility controls.
sow: software-factories-masterclass-SOW-02
"""
import hashlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import factory
import scratch
import collect


class PackControls(unittest.TestCase):
    def setUp(self):
        cache = Path(__file__).resolve().parent / '.pack-test-cache'
        cache.mkdir(exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(dir=cache)
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.pack = self.root / 'pack'
        for name in ('product/briefing', 'product/tests', 'acceptance', 'builder', 'tasks'):
            (self.pack / name).mkdir(parents=True, exist_ok=True)
        (self.pack / 'product/briefing/market.py').write_text('not_ready = True\n')
        (self.pack / 'builder/AGENTS-a6.md').write_text('Only allowed files.')
        suite = self.pack / 'acceptance/check.py'
        suite.write_text('pinned verifier fixture')
        self.task = {'id': 'A6-fixture', 'request': 'Make a market card.', 'allowed_paths': ['product/briefing/market.py', 'product/tests/'],
                     'excluded': 'Protected gate', 'support': [],
                     'acceptance': {'path': 'acceptance/check.py', 'sha256': hashlib.sha256(suite.read_bytes()).hexdigest()}}
        self.task_path = self.pack / 'tasks/a6-fixture.json'
        self.task_path.write_text(json.dumps(self.task))
        self.environment = self.root / 'environment.json'
        self.environment.write_text('{}')
        self.candidate = self.root / 'candidate'
        (self.candidate / 'product/briefing').mkdir(parents=True)
        (self.candidate / 'product/briefing/market.py').write_text('ready = True\n')

    def test_task_b_limit_is_visible_but_protected_metadata_is_not(self):
        task = {**self.task, 'limit': 2}
        visible = scratch.visible_task(task)
        self.assertEqual(visible['limit'], 2)
        self.assertNotIn('acceptance', visible)
        self.assertNotIn('support', visible)
        for invalid in (None, True, 0, 4, '2'):
            with self.subTest(limit=invalid), self.assertRaises(ValueError):
                scratch.visible_task({**task, 'limit': invalid})

    def test_a6_profile_requires_supported_stable_core_and_records_actual_version(self):
        profile = Path(factory.__file__).with_name('environment-a6.json')
        with patch.object(factory.platform, 'python_version_tuple', return_value=('3', '12', '0')), \
                patch.object(factory.importlib.metadata, 'version', return_value='0.35.2'), \
                patch.object(factory.importlib.util, 'find_spec', return_value=object()):
            versions, problems = factory.prepare(profile)
        self.assertEqual(versions, {'zeocore': '0.35.2'})
        self.assertEqual(problems, [])
        with patch.object(factory.importlib.metadata, 'version', return_value='0.34.0'), \
                patch.object(factory.importlib.util, 'find_spec', return_value=object()):
            _, problems = factory.prepare(profile)
        self.assertTrue(problems)

    def test_existing_preparer_builds_only_visible_nested_pack_and_collect_uses_that_base(self):
        workspace = self.root / 'scratch'
        self.assertEqual(scratch.main(self.task_path, workspace, pack_root=self.pack, instructions='AGENTS-a6.md'), 0)
        visible = json.loads((workspace / 'tasks/a6-fixture.json').read_text())
        self.assertNotIn('acceptance', visible)
        self.assertFalse((workspace / 'acceptance').exists())
        self.assertEqual((workspace / 'AGENTS.md').read_text(), 'Only allowed files.')
        (workspace / 'product/briefing/market.py').write_text('ready = True\n')
        review = self.root / 'review'
        output = self.root / 'collected'
        self.assertEqual(collect.main(workspace, output, review, pack_root=self.pack), 0)
        self.assertEqual(json.loads((review / 'review.json').read_text())['files_changed'], ['product/briefing/market.py'])

    def inspect_task_snapshot(self, test_path, project, workspace, **kwargs):
        copied = Path(workspace) / 'tasks' / self.task_path.name
        self.assertEqual(copied.read_bytes(), self.task_path.read_bytes())
        return {'passed': True, 'summary': 'OK', 'output': ''}

    def test_same_factory_records_pack_baseline_pin_diff_and_strict_protected_gate(self):
        run = self.root / 'run'
        with patch.object(factory, 'prepare', return_value=({'zeocore': '0.35.2'}, [])), \
                patch.object(factory, 'run_tests', side_effect=self.inspect_task_snapshot) as gate:
            self.assertEqual(factory.main(self.task_path, self.candidate, run,
                                          environment_path=self.environment, pack_root=self.pack, strict=True), 0)
        decision = json.loads((run / 'decision.json').read_text())
        self.assertEqual(decision['baseline_digest'], factory.digest_tree(self.pack / 'product'))
        self.assertEqual(decision['decision'], 'ACCEPT')
        self.assertTrue(gate.call_args.kwargs['strict'])
        self.assertEqual(gate.call_count, 1)  # no unconfined candidate tests

    def test_bad_pin_is_error_not_candidate_reject_and_prefix_confusion_rejects(self):
        task = {**self.task, 'acceptance': {**self.task['acceptance'], 'sha256': 'wrong'}}
        self.task_path.write_text(json.dumps(task))
        with patch.object(factory, 'prepare', return_value=('injected', [])), patch.object(factory, 'run_tests') as gate:
            self.assertEqual(factory.main(self.task_path, self.candidate, self.root / 'bad-pin',
                                          environment_path=self.environment, pack_root=self.pack, strict=True), 2)
            gate.assert_not_called()
        self.task_path.write_text(json.dumps(self.task))
        (self.candidate / 'product/briefing/market.py.evil').write_text('outside allowed file')
        with patch.object(factory, 'prepare', return_value=('injected', [])), patch.object(factory, 'run_tests') as gate:
            self.assertEqual(factory.main(self.task_path, self.candidate, self.root / 'bad-scope',
                                          environment_path=self.environment, pack_root=self.pack, strict=True), 1)
            gate.assert_not_called()

    def test_strict_completion_needs_nonzero_tests_and_ok_from_verifier(self):
        for code, stderr, expected in [(0, 'Ran 14 tests in 0.1s\n\nOK\n', True),
                                       (0, 'Ran 0 tests in 0.1s\n\nOK\n', False),
                                       (0, 'forged OK\n', False), (1, 'Ran 14 tests in 0.1s\nOK\n', False)]:
            with self.subTest(stderr=stderr), patch.object(factory.subprocess, 'run', return_value=SimpleNamespace(returncode=code, stderr=stderr)) as call:
                result = factory.run_tests(self.pack / 'acceptance/check.py', self.pack / 'product', self.root, strict=True)
                self.assertEqual(result['passed'], expected)
                self.assertIn('-I', call.call_args.args[0])
                self.assertEqual(call.call_args.kwargs['env']['PRODUCT_PROJECT'], str(self.pack / 'product'))
                self.assertNotIn('OPENAI_API_KEY', call.call_args.kwargs['env'])


if __name__ == '__main__':
    unittest.main()
