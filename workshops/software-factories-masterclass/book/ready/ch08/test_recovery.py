"""Meaningful fault and evidence controls for the complete offline lesson.
sow: software-factories-masterclass-SOW-02
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent


class LessonControls(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'lesson'
        shutil.copytree(ROOT, self.root, ignore=shutil.ignore_patterns(
            '.venv', '__pycache__', 'attempts', 'runs', 'examples', 'recovery-runs', 'ledger.json'))
        self.env = {'PATH': os.environ.get('PATH', ''), 'PYTHONDONTWRITEBYTECODE': '1',
                    'TMPDIR': self.temp.name, 'HOME': self.temp.name}

    def run_command(self, *arguments):
        result = subprocess.run([sys.executable, *arguments], cwd=self.root,
                                env=self.env, text=True, capture_output=True, timeout=30)
        return result.returncode, result.stdout + result.stderr

    def exercise(self, count):
        for args, expected in ((('lesson.py', 'check'), 1), (('lesson.py', 'see'), 0),
                               (('set_request.py', str(count)), 0), (('lesson.py', 'build'), 0),
                               (('lesson.py', 'measure'), 0)):
            code, output = self.run_command(*args)
            self.assertEqual(code, expected, output)
        code, output = self.run_command('lesson.py', 'recover')
        self.assertEqual(code, 4 if count == 1 else 0, output)
        ledger = self.root / 'ledger.json'
        before = ledger.read_bytes()
        code, output = self.run_command('lesson.py', 'recover')
        self.assertEqual(code, 4 if count == 1 else 0, output)
        self.assertIn('invocation: 0', output)
        self.assertEqual(ledger.read_bytes(), before)
        code, output = self.run_command('lesson.py', 'check')
        self.assertEqual(code, 0, output)

    def test_three_attempts_recover_and_changed_export_fails_completion(self):
        self.exercise(3)
        target = self.root / 'attempts/mine/product/recovery.json'
        target.write_text('{"max_attempts": 1, "retry_rejected": false}')
        self.assertEqual(self.run_command('lesson.py', 'check')[0], 1)

    def test_one_attempt_escalates_and_changed_verifier_fails_completion(self):
        self.exercise(1)
        verifier = self.root / 'factory_engine/factory.py'
        verifier.write_text(verifier.read_text() + '\n# changed verifier\n')
        self.assertEqual(self.run_command('lesson.py', 'check')[0], 1)

    def test_real_reject_is_terminal_and_does_not_retry(self):
        self.assertEqual(self.run_command('set_request.py', '3')[0], 0)
        shutil.copytree(self.root / 'product', self.root / 'attempts/wrong/product')
        args = ('recover.py', 'tasks/c-recovery-attempts.json', 'attempts/wrong', 'ledger.json')
        code, output = self.run_command(*args)
        self.assertEqual(code, 1, output)
        entry = next(iter(json.loads((self.root / 'ledger.json').read_text()).values()))
        self.assertEqual(entry['final'], 'REJECT')
        self.assertEqual(len(entry['attempts']), 1)
        code, output = self.run_command(*args)
        self.assertEqual(code, 1, output)
        self.assertIn('nothing was run', output)

    def test_corrupted_verifier_is_error_and_unallowed_file_is_rejected(self):
        self.assertEqual(self.run_command('scripted_builder.py', 'tasks/c-recovery-attempts.json', 'attempts/good')[0], 0)
        suite = self.root / 'acceptance/c_recovery_policy.py'
        suite.write_text(suite.read_text() + '\n# changed protected suite\n')
        code, output = self.run_command('judge.py', 'tasks/c-recovery-attempts.json', 'attempts/good', 'runs/tamper')
        self.assertEqual(code, 2, output)
        decision = json.loads((self.root / 'runs/tamper/decision.json').read_text())
        self.assertEqual(decision['decision'], 'ERROR')
        # A supplied extra file is outside the public allowlist, even if benign.
        shutil.copyfile(ROOT / 'acceptance/c_recovery_policy.py', suite)
        (self.root / 'attempts/good/product/extra.json').write_text('{}')
        code, output = self.run_command('judge.py', 'tasks/c-recovery-attempts.json', 'attempts/good', 'runs/extra')
        self.assertEqual(code, 1, output)


if __name__ == '__main__':
    unittest.main()
