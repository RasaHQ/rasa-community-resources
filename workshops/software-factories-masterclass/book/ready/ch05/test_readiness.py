"""Unsupported machines must not produce product verdicts.
"""
import contextlib
import io
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'factory_engine'))
import factory


class ReadinessControls(unittest.TestCase):
    def test_gate_without_sandbox_exits_two_before_reading_task(self):
        result = subprocess.run([sys.executable, str(ROOT / 'run_a6.py'), 'not-a-task', 'not-an-attempt'],
                                env={'PATH': '/no-sandbox-here'}, capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn('could not run: this check needs macOS', result.stdout)
        self.assertNotIn('REJECT', result.stdout)
        self.assertEqual(result.stderr, '')

    def test_full_factory_without_required_sandbox_never_tests_candidate(self):
        with patch.object(factory.platform, 'system', return_value='Linux'), \
                patch.object(factory, 'run_tests') as tests, \
                patch.object(factory, 'prepare') as prepare, contextlib.redirect_stdout(io.StringIO()) as output:
            code = factory.main(ROOT / 'tasks/b-limit-currencies.json', ROOT / 'not-an-attempt',
                                ROOT / 'never-created-by-readiness-control', pack_root=ROOT,
                                environment_path=ROOT / 'factory_engine/environment-a6.json', strict=True)
        self.assertEqual(code, 2)
        self.assertIn('could not run: this check needs macOS', output.getvalue())
        prepare.assert_not_called()
        tests.assert_not_called()
        self.assertFalse((ROOT / 'never-created-by-readiness-control').exists())


if __name__ == '__main__':
    unittest.main()
