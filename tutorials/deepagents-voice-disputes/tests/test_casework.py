import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'shared'))
from bank_research.casework import CaseSession


class CaseBoundary(unittest.TestCase):
    def setUp(self):
        self.session = CaseSession()

    def ready(self, tx='TX-101'):
        self.session.verify_demo('111111')
        self.session.select(tx)
        return self.session.prepare()

    def submit(self, proposal):
        return self.session.submit(*(proposal[k] for k in ('proposal_id', 'merchant', 'amount', 'currency', 'date')))

    def test_unverified_cannot_select(self):
        self.assertEqual(self.session.select('TX-101'), {'error': 'transaction_unavailable'})

    def test_other_identity_refused_without_disclosure(self):
        self.session.verify_demo('111111')
        self.assertEqual(self.session.select('TX-201'), {'error': 'transaction_unavailable'})
        self.assertIsNone(self.session.selected)

    def test_cannot_switch_verified_identity(self):
        self.session.verify_demo('111111')
        self.assertIn('error', self.session.verify_demo('222222'))
        self.assertEqual(self.session.owner, 'demo-a')

    def test_correction_invalidates_old_proposal(self):
        first = self.ready()
        self.session.select('TX-102')
        self.assertIn('error', self.submit(first))
        second = self.session.prepare()
        self.assertNotEqual(first['proposal_id'], second['proposal_id'])
        self.assertEqual(self.submit(second)['transaction_id'], 'TX-102')

    def test_denied_correction_also_invalidates(self):
        first = self.ready()
        self.session.select('TX-201')
        self.assertIn('error', self.submit(first))
        self.assertEqual(self.session.submitted, {})

    def test_changed_readback_cannot_record(self):
        first = self.ready()
        first['amount'] = '149.00'
        self.assertEqual(self.submit(first), {'error': 'readback_changed'})
        self.assertEqual(self.session.submitted, {})

    def test_repeated_submission_has_one_reference(self):
        first = self.ready()
        self.assertEqual(self.session.prepare(), first)
        self.assertEqual(self.submit(first), self.submit(first))
        self.assertEqual(len(self.session.submitted), 1)

    def test_research_snapshot_has_no_customer_owner(self):
        self.ready()
        data = self.session.evidence()
        self.assertNotIn('owner', data['transaction'])
        data['transaction']['amount'] = '0.00'
        self.assertEqual(self.session.evidence()['transaction']['amount'], '49.00')

    def test_model_cannot_prepare_via_evidence(self):
        self.ready()
        self.session.proposal = None
        self.session.evidence()
        self.assertIsNone(self.session.proposal)
        self.assertEqual(self.session.submitted, {})


if __name__ == '__main__':
    unittest.main()
