import itertools
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from refund_allocation import allocate, Refunds, dynamic_returns, TOTAL, WEIGHTS, demo


class RefundAllocation(unittest.TestCase):
    def test_same_rounding_method_changes_item_after_removing_another(self):
        self.assertEqual(allocate(TOTAL,WEIGHTS), {'A':61,'B':60,'C':182})
        self.assertEqual(dynamic_returns(TOTAL,WEIGHTS,['A','B','C']), {'A':61,'B':61,'C':181})

    def test_fixed_item_amounts_survive_all_return_orders(self):
        expected=allocate(TOTAL,WEIGHTS)
        for order in itertools.permutations(WEIGHTS):
            ledger=Refunds(TOTAL,WEIGHTS)
            actual={item:ledger.refund(item,item) for item in order}
            self.assertEqual(actual,expected); self.assertEqual(sum(actual.values()),TOTAL)

    def test_dynamic_orders_conserve_total_despite_item_disagreement(self):
        for order in itertools.permutations(WEIGHTS):
            self.assertEqual(sum(dynamic_returns(TOTAL,WEIGHTS,order).values()),TOTAL)
        self.assertGreater(demo()['orders_changing_an_item'],0)

    def test_integer_conservation_for_bounded_input_family(self):
        for weights in itertools.product(range(1,5),repeat=3):
            for total in range(31):
                result=allocate(total,dict(zip('ABC',weights)))
                self.assertEqual(sum(result.values()),total)
                self.assertTrue(all(type(v) is int and v>=0 for v in result.values()))

    def test_replay_and_request_collision(self):
        ledger=Refunds(TOTAL,WEIGHTS)
        self.assertEqual(ledger.refund('r1','A'),61)
        self.assertEqual(ledger.refund('r1','A'),61)
        with self.assertRaises(ValueError): ledger.refund('r1','B')
        with self.assertRaises(ValueError): ledger.refund('r2','A')

    def test_invalid_inputs_and_missing_item_are_rejected(self):
        for total,weights in [(-1,WEIGHTS),(True,WEIGHTS),(1,{}),(1,{'A':0}),(1,{'A':True})]:
            with self.assertRaises(ValueError): allocate(total,weights)
        with self.assertRaises(ValueError): Refunds(TOTAL,WEIGHTS).refund('r','missing')

    def test_tie_break_uses_identity_not_input_order(self):
        self.assertEqual(allocate(1,{'B':1,'A':1}),{'B':0,'A':1})


if __name__ == '__main__': unittest.main()
