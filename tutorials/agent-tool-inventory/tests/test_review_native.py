import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]


class NativeReviewControls(unittest.TestCase):
    def call(self, *extra):
        return subprocess.run(
            [sys.executable, '-B', str(ROOT / 'compare_lookup_review.py'),
             '--project', str(ROOT), '--skill', 'review_record', '--tool', 'record_review', *extra],
            capture_output=True, text=True, env=os.environ.copy(), timeout=30,
        )

    def test_trust_acknowledgement_precedes_loading(self):
        result = self.call()
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, '')
        self.assertIn('--trusted-python is required', result.stderr)

    def test_current_native_binding_produces_the_comparison(self):
        result = self.call('--trusted-python')
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report['modelOnlyFalseMissingGateReports'], 1)
        targets = {r['target']: r for r in report['targets']}
        self.assertEqual(set(targets), {'(prose)', 'review_record__finish_review'})
        inline = targets['review_record__finish_review']
        self.assertTrue(inline['modelOnlyReviewRequestsGateFix'])
        self.assertFalse(inline['engineConfigurationReviewRequestsGateFix'])
        self.assertTrue(all(r['userApprovalObserved'] is None for r in targets.values()))
