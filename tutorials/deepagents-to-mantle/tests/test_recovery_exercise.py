"""Check the public recovery command and the questions its queries answer."""
import json
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]


class RecoveryExercise(unittest.TestCase):
    def test_cli_distinguishes_late_trim_smaller_generation_and_summaries(self):
        result = subprocess.run(
            [sys.executable, '-I', '-S', '-B', str(ROOT / 'exercises/recover_result.py')],
            capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertTrue(report['databaseUnchanged'])
        cases = {row['case']: row['result'] for row in report['cases']}
        self.assertEqual(len(cases), 4)
        self.assertEqual(cases['trim-after-generation']['reason'], 'sqlite_value_too_large')
        self.assertNotIn('rows', cases['trim-after-generation'])
        self.assertEqual(cases['generate-smaller-value']['rows'], [['0' * 80]])
        self.assertEqual(cases['summarise-six-values']['rows'], [[6, 72000]])
        self.assertEqual(cases['summarise-escaped-values']['rows'], [[8, 12000]])
        for name in ('summarise-six-values', 'summarise-escaped-values'):
            self.assertEqual(cases[name]['columns'], ['row_count', 'character_count'])


if __name__ == '__main__':
    unittest.main()
