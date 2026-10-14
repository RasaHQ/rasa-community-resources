"""Isolate the final hardship check. Fixture-only; no SDK, network or payment."""
import ast
import inspect
import json
import unittest
from unittest.mock import patch
import test_guard as t


def without_final_hardship_check():
    tree = ast.parse(inspect.getsource(t.rp.confirmation_facts))
    function = tree.body[0]
    index = next(i for i, node in enumerate(function.body) if isinstance(node, ast.If))
    first = function.body[index]
    if not isinstance(first, ast.If) or ast.unparse(first.test) != (
        'hardship_declared(conversation.user_texts) or state.open_referral()'
    ):
        raise AssertionError('The expected final hardship predicate changed')
    function.body.pop(index)
    namespace = dict(vars(t.rp))
    exec(compile(tree, '<deliberately-broken-confirmation-check>', 'exec'), namespace)
    return namespace['confirmation_facts']


def acquire(hardship, broken=False):
    case = t.SelectAndRecordTests()
    case.setUp()
    # Start with a genuinely valid staged offer, memory tag and read-back.
    _, memory = case.stage('OFR-4471-6M')
    users = ('No me alcanza para la renta.', 'Bueno, anóteme en el de seis pagos.') if hardship else ('Quiero seis pagos.',)
    replacement = without_final_hardship_check() if broken else t.rp.confirmation_facts
    with patch.object(t.rp, 'confirmation_facts', replacement):
        result = case.record('OFR-4471-6M', memory, users=users)
    return {'status': result['status'], 'effects': result['effects'],
            'plan_recorded': case.state.active_plan() is not None,
            'referral_open': case.state.open_referral() is not None,
            'payment_status': result.get('payment_status'),
            'reason': result.get('reason'), 'detail': result.get('detail')}


class FinalConfirmationBoundary(unittest.TestCase):
    def test_valid_confirmation_records_a_plan(self):
        result = acquire(False)
        self.assertEqual((result['status'], result['effects'], result['plan_recorded']), ('succeeded', 1, True))
        self.assertEqual(result['payment_status'], 'no_payment_received')

    def test_final_hardship_check_prevents_recording(self):
        result = acquire(True)
        self.assertEqual((result['status'], result['effects'], result['plan_recorded']), ('blocked', 0, False))
        self.assertEqual(result['reason'], 'choice_not_confirmed')
        self.assertEqual(result['detail'], 'hardship_declared')
        # Blocking the plan does not itself create a human referral.
        self.assertFalse(result['referral_open'])

    def test_removing_only_final_check_records_despite_hardship(self):
        result = acquire(True, broken=True)
        self.assertEqual((result['status'], result['effects'], result['plan_recorded']), ('succeeded', 1, True))
        self.assertEqual(result['payment_status'], 'no_payment_received')


if __name__ == '__main__':
    unittest.main()
