import copy
import json
from pathlib import Path
import unittest
from compare_lookup_review import compare


class ReviewQuestionControls(unittest.TestCase):
    def setUp(self):
        self.snapshot = json.loads((Path(__file__).resolve().parents[1] / 'inventory.json').read_text())

    def test_native_fixture_has_one_false_missing_engine_gate_report(self):
        report = compare(self.snapshot, 'review_record', 'record_review')
        self.assertEqual(report['modelOnlyFalseMissingGateReports'], 1)
        rows = {r['target']: r for r in report['targets']}
        inline = rows['review_record__finish_review']
        self.assertTrue(inline['modelOnlyReviewRequestsGateFix'])
        self.assertFalse(inline['engineConfigurationReviewRequestsGateFix'])
        self.assertTrue(all(r['userApprovalObserved'] is None for r in rows.values()))

    def test_engine_removal_changes_correct_question_not_model_only_answer(self):
        changed = copy.deepcopy(self.snapshot)
        row = next(r for r in changed['rows'] if r['tool'] == 'record_review' and r['target'] != '(prose)')
        row['engineConfirmationSetting'] = False
        report = compare(changed, 'review_record', 'record_review')
        inline = next(r for r in report['targets'] if r['target'] != '(prose)')
        self.assertTrue(inline['modelOnlyReviewRequestsGateFix'])
        self.assertTrue(inline['engineConfigurationReviewRequestsGateFix'])
        self.assertFalse(inline['modelOnlyFalseMissingGateReport'])
        self.assertIsNone(inline['userApprovalObserved'])

    def test_missing_lookup_is_not_assumed_disabled(self):
        del self.snapshot['rows'][1]['engineConfirmationSetting']
        with self.assertRaisesRegex(ValueError, 'booleans'):
            compare(self.snapshot, 'review_record', 'record_review')

    def test_unresolved_inventory_refused(self):
        self.snapshot['unresolved'] = [{'tool': 'missing'}]
        with self.assertRaisesRegex(ValueError, 'resolved'):
            compare(self.snapshot, 'review_record', 'record_review')


    def test_non_object_snapshot_is_refused(self):
        with self.assertRaisesRegex(ValueError, 'resolved'):
            compare([], 'review_record', 'record_review')

    def test_malformed_rows_are_refused(self):
        self.snapshot['rows'] = ['not a binding']
        with self.assertRaisesRegex(ValueError, 'objects'):
            compare(self.snapshot, 'review_record', 'record_review')

    def test_duplicate_target_cannot_inflate_the_report(self):
        self.snapshot['rows'].append(copy.deepcopy(self.snapshot['rows'][1]))
        with self.assertRaisesRegex(ValueError, 'Duplicate targets'):
            compare(self.snapshot, 'review_record', 'record_review')


if __name__ == '__main__':
    unittest.main()
