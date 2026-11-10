"""Constructed state tests; no model, SDK, licence or historical-run claims."""
from __future__ import annotations

import sys
import unittest
from copy import deepcopy
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from lib import recovery
from exercises.release_decision import ReleaseReview, UnboundAnswerControl

PASSENGER = 'HT-PAX-3308'
MIAMI = 'HT-HLD-4K7M'


class ReleaseReviewTests(unittest.TestCase):
    def setUp(self):
        self.service = recovery.Disruption()
        self.review = ReleaseReview(self.service, PASSENGER)

    def test_refusal_preserves_hold_and_inventory(self):
        inventory = deepcopy(self.service.inventory)
        pending = self.review.propose(MIAMI)
        result = self.review.decide(pending['proposal_id'], 'decline')
        self.assertEqual(result['status'], 'declined')
        self.assertEqual(recovery.check_hold(self.service, PASSENGER, MIAMI)['status'], 'active')
        self.assertEqual(self.service.inventory, inventory)

    def test_an_unbound_acceptance_cannot_release_a_hold(self):
        self.review.propose(MIAMI)
        self.assertEqual(self.review.decide('another-question', 'accept')['status'], 'blocked')
        self.assertEqual(recovery.check_hold(self.service, PASSENGER, MIAMI)['status'], 'active')

    def test_correction_retires_the_old_question_before_acceptance(self):
        recovery.find_recovery_options(self.service, PASSENGER, 'Chicago')
        selected = recovery.select_option(self.service, PASSENGER, 'OPT-ORD-315')
        self.assertEqual(selected['status'], 'selected')
        held = recovery.hold_recovery_option(self.service, PASSENGER, 'OPT-ORD-315', 'OPT-ORD-315', 'constructed-review')
        self.assertEqual(held['status'], 'held')
        other = held['hold_id']
        old = self.review.propose(MIAMI)
        current = self.review.propose(other)
        inventory = deepcopy(self.service.inventory)
        self.assertEqual(self.review.decide(old['proposal_id'], 'accept')['status'], 'superseded')
        self.assertEqual(self.service.inventory, inventory)
        self.assertEqual(recovery.check_hold(self.service, PASSENGER, MIAMI)['status'], 'active')
        self.assertEqual(recovery.check_hold(self.service, PASSENGER, other)['status'], 'active')
        self.assertEqual(self.review.decide(current['proposal_id'], 'accept')['hold_id'], other)
        self.assertEqual(recovery.check_hold(self.service, PASSENGER, MIAMI)['status'], 'active')
        self.assertEqual(recovery.check_hold(self.service, PASSENGER, other)['status'], 'released')

    def test_replayed_acceptance_returns_receipt_without_another_inventory_change(self):
        pending = self.review.propose(MIAMI)
        receipt = self.review.decide(pending['proposal_id'], 'accept')
        inventory = deepcopy(self.service.inventory)
        repeated = self.review.decide(pending['proposal_id'], 'accept')
        self.assertEqual(repeated['hold_id'], receipt['hold_id'])
        self.assertEqual(repeated['status'], 'released')
        self.assertTrue(repeated['replay'])
        self.assertEqual(self.service.inventory, inventory)

    def test_direct_service_control_releases_without_application_decision(self):
        # Same initial fixture: bypassing the application check really changes
        # state. The protected path's no-effect assertions are not vacuous.
        result = recovery.release_hold(self.service, PASSENGER, MIAMI)
        self.assertEqual(result['status'], 'released')
        self.assertEqual(recovery.check_hold(self.service, PASSENGER, MIAMI)['status'], 'released')

    def test_another_passengers_hold_is_not_proposed(self):
        self.assertEqual(self.review.propose('HT-HLD-77Q9')['status'], 'blocked')
        self.assertIsNone(self.review.pending)

    def test_accept_after_refusal_does_not_reopen_the_completed_decision(self):
        question = self.review.propose(MIAMI)
        self.review.decide(question['proposal_id'], 'decline')
        result = self.review.decide(question['proposal_id'], 'accept')
        self.assertEqual(result['status'], 'declined')
        self.assertTrue(result['replay'])
        self.assertEqual(recovery.check_hold(self.service, PASSENGER, MIAMI)['status'], 'active')

    def test_reasking_about_same_hold_retires_the_first_question(self):
        old = self.review.propose(MIAMI)
        current = self.review.propose(MIAMI)
        result = self.review.decide(old['proposal_id'], 'accept')
        self.assertEqual(result['status'], 'superseded')
        self.assertTrue(result['replay'])
        self.assertEqual(recovery.check_hold(self.service, PASSENGER, MIAMI)['status'], 'active')
        self.assertEqual(self.review.decide(current['proposal_id'], 'accept')['status'], 'released')

    def test_unbound_control_releases_current_hold_for_an_old_answer(self):
        control = UnboundAnswerControl(self.service, PASSENGER)
        old = control.propose(MIAMI)
        control.propose(MIAMI)
        self.assertEqual(control.decide(old['proposal_id'], 'accept')['status'], 'released')
        self.assertEqual(recovery.check_hold(self.service, PASSENGER, MIAMI)['status'], 'released')


if __name__ == '__main__':
    unittest.main()
