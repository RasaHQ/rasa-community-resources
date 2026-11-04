import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from shift_intake import submit, persisted


class AbsenceIntake(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'intake.db'

    def send(self, **kwargs):
        args = dict(path=self.path, request='a1', employee='e1', shift='night1',
                    replacement='e2', qualified=False)
        args.update(kwargs)
        return submit(**args)

    def test_single_transaction_denial_erases_useful_report(self):
        self.assertEqual(self.send(separate=False)['request'], 'denied')
        self.assertEqual(persisted(self.path), {'absence': [], 'swaps': []})

    def test_separate_denial_retains_report_after_reopen(self):
        self.assertEqual(self.send()['absence'], 'recorded')
        self.assertEqual(persisted(self.path), {'absence': [('a1', 'e1', 'night1')], 'swaps': []})

    def test_success_retains_both_records(self):
        self.assertEqual(self.send(qualified=True)['swap'], 'approved_in_fixture')
        self.assertEqual(persisted(self.path)['swaps'], [('a1', 'e2')])

    def test_same_absence_retry_does_not_duplicate(self):
        self.send(); self.send()
        self.assertEqual(len(persisted(self.path)['absence']), 1)

    def test_identity_collision_does_not_change_report(self):
        self.send()
        with self.assertRaisesRegex(ValueError, 'another absence'):
            self.send(shift='night2')
        self.assertEqual(persisted(self.path)['absence'], [('a1', 'e1', 'night1')])

    def test_intake_without_replacement_is_still_recorded(self):
        self.assertEqual(self.send(replacement=None)['swap'], 'denied')
        self.assertEqual(len(persisted(self.path)['absence']), 1)

    def test_later_eligible_replacement_can_resolve_denied_swap(self):
        self.send()
        self.send(qualified=True)
        self.assertEqual(len(persisted(self.path)['absence']), 1)
        self.assertEqual(persisted(self.path)['swaps'], [('a1', 'e2')])

    def test_resolved_swap_replay_cannot_replace_person(self):
        self.send(qualified=True)
        self.assertEqual(self.send(qualified=True, replacement='e3')['swap'], 'denied')
        self.assertEqual(persisted(self.path)['swaps'], [('a1', 'e2')])

    def test_truthy_string_is_not_qualification(self):
        self.assertEqual(self.send(qualified='yes')['swap'], 'denied')
        self.assertEqual(persisted(self.path)['swaps'], [])

    def test_invalid_report_is_not_acknowledged(self):
        with self.assertRaises(ValueError): self.send(employee='')
        self.assertEqual(persisted(self.path)['absence'], [])


if __name__ == '__main__':
    unittest.main()
