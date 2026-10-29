"""Real protected-gate integration cases."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import factory_gate


class FactoryGateTests(unittest.TestCase):
    def protected_hashes(self):
        root = factory_gate._pack()
        return {str(path): hashlib.sha256(path.read_bytes()).hexdigest()
                for path in root.rglob('*') if path.is_file() and '__pycache__' not in path.parts}

    def test_good_attempt_accepts_and_preserves_the_source(self):
        before = self.protected_hashes()
        result = factory_gate.run_factory('good')
        self.assertEqual(result['verdict'], 'ACCEPT', result)
        self.assertIsNone(result['failing_test'])
        self.assertRegex(result['fingerprint'], r'^[0-9a-f]{64}$')
        self.assertGreater(result['seconds'], 0)
        self.assertEqual(self.protected_hashes(), before)

    def test_ignoring_limit_rejects_with_b1_and_preserves_the_source(self):
        before = self.protected_hashes()
        result = factory_gate.run_factory('ignores-limit')
        self.assertEqual(result['verdict'], 'REJECT', result)
        self.assertEqual(result['failing_test'], 'test_b1_four_currencies_show_at_most_the_limit')
        self.assertRegex(result['fingerprint'], r'^[0-9a-f]{64}$')
        self.assertGreater(result['seconds'], 0)
        self.assertEqual(self.protected_hashes(), before)

    def test_failed_live_builds_consume_slots_and_never_run_gate_or_leak_key(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            keyfile = root / 'credentials.env'
            keyfile.write_text('OPENAI_API_KEY=unit-test-placeholder\n')
            calls = []

            def command(args, cwd, timeout, **kwargs):
                calls.append((args, kwargs))
                if args[0] == '-c':
                    self.assertNotIn('key', kwargs)
                    return 0, '', ''
                self.assertEqual(args[0], 'build.py')
                self.assertEqual(kwargs['key'], 'unit-test-placeholder')
                return 2, 'failed build', 'private details must not be returned'

            environment_before = dict(os.environ)
            with patch.object(factory_gate, '_run', command):
                for _ in range(4):
                    result = factory_gate.run_factory('good', mode='live', evidence_root=root,
                                                      env_file=keyfile, max_funded_runs=3)
                    self.assertEqual(result['verdict'], 'NOT_READY')
                    self.assertEqual(result['fingerprint'], '')
                    self.assertNotIn('placeholder', json.dumps(result))
                    self.assertNotIn('private details', json.dumps(result))
            self.assertEqual(sum(args[0] == 'build.py' for args, _ in calls), 3)
            self.assertEqual(json.loads((root / 'funded-runs.json').read_text())['used'], 3)
            self.assertEqual(dict(os.environ), environment_before)

    def test_concurrent_live_call_does_not_start_another_builder(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with (root / 'funded.lock').open('a') as lock:
                factory_gate.fcntl.flock(lock, factory_gate.fcntl.LOCK_EX | factory_gate.fcntl.LOCK_NB)
                with patch.object(factory_gate, '_run', side_effect=AssertionError('must not spawn')):
                    result = factory_gate.run_factory('good', mode='LIVE', evidence_root=root)
                self.assertEqual(result['verdict'], 'NOT_READY')
                self.assertIn('busy', result['reason'])

    def test_bad_attempt_never_funds_a_live_build(self):
        with patch.object(factory_gate, '_live', side_effect=AssertionError('must not fund')):
            result = factory_gate.run_factory('ignores-limit', mode='LIVE')
        self.assertEqual(result['mode'], 'SCRIPTED')
        self.assertEqual(result['verdict'], 'REJECT')
        self.assertEqual(result['builder_calls'], 0)


if __name__ == '__main__':
    unittest.main()
