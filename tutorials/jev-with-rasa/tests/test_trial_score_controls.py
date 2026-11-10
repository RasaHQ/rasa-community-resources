"""Detect fixture aliasing rather than averaging a wrong read into a threshold."""
import copy
import unittest
from jacaranda_jev.score_controls import capture_controls, score


class TrialScoreControls(unittest.TestCase):
    def test_identical_payloads_approve_the_wrong_account(self):
        records = capture_controls()
        self.assertEqual(records[0]['transactions'], records[1]['transactions'])
        self.assertNotEqual(records[0]['actual_account'], records[1]['actual_account'])
        result = score(records)
        self.assertEqual(result['payload_matches'], 2)
        self.assertEqual(result['account_bound_matches'], 1)
        self.assertEqual(result['payload_only_decision'], 'APPROVE')
        self.assertEqual(result['account_bound_decision'], 'REJECT')
        self.assertEqual(result['external_provider_requests'], 0)

    def test_fixing_actual_account_changes_acceptance(self):
        records = capture_controls()
        wrong = next(r for r in records if r['case'] == 'wrong_eligible')
        wrong['actual_account'] = 'A-CURRENT'
        wrong['account_reads'] = ['A-CURRENT']
        self.assertEqual(score(records)['account_bound_decision'], 'APPROVE')

    def test_distinguishable_fixture_rows_expose_payload_only_limit(self):
        records = capture_controls()
        wrong = next(r for r in records if r['case'] == 'wrong_eligible')
        wrong['transactions'][0]['amount'] = '8.50'
        result = score(records)
        self.assertEqual(result['payload_only_decision'], 'REJECT')
        self.assertEqual(result['account_bound_decision'], 'REJECT')
        current = next(case for case in result['cases'] if case['case'] == 'current')
        self.assertTrue(current['payload_matches'])
        self.assertTrue(current['account_bound_matches'])

    def test_duplicate_cases_cannot_pad_checks(self):
        records = capture_controls()
        with self.assertRaisesRegex(ValueError, 'two distinct'):
            score([copy.deepcopy(records[0]), copy.deepcopy(records[0])])
