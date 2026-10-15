"""Literal examples of the written policy; no inference or payment service."""
import unittest
from dataclasses import replace
from shop_adviser.refund_policy import ReturnRecord, assess_refund


class PolicyExamples(unittest.TestCase):
    def setUp(self):
        self.order = ReturnRecord("WS-RETURN-01", "customer-a", 1299, 20,
                                  "sealed", "inspection-01")

    def test_policy_examples(self):
        offer = {"status": "full_refund_offer", "amount_minor": 1299, "currency": "GBP"}
        outside = {"status": "staff_review", "reason": "outside_automatic_window"}
        cases = [
            ("sealed inside window", self.order, offer),
            ("last included day", replace(self.order, received_day=30), offer),
            ("first excluded day", replace(self.order, received_day=31), outside),
            ("defect inside window", replace(self.order, condition="confirmed_defect"), offer),
            ("defect outside window", replace(self.order, received_day=34, condition="confirmed_defect"), outside),
            ("inspection absent", replace(self.order, condition=None, inspection_ref=None), {"status": "awaiting_inspection"}),
            ("condition without inspection", replace(self.order, inspection_ref=None), {"status": "awaiting_inspection"}),
            ("other condition", replace(self.order, condition="opened"), {"status": "staff_review", "reason": "condition_needs_review"}),
        ]
        for label, record, expected in cases:
            with self.subTest(label):
                self.assertEqual(assess_refund(record, "customer-a"), expected)

    def test_other_customer_and_absent_order_disclose_the_same_result(self):
        self.assertEqual(assess_refund(self.order, "customer-b"), {"status": "unknown_order"})
        self.assertEqual(assess_refund(None, "customer-a"), {"status": "unknown_order"})

    def test_offer_uses_recorded_payment_not_a_model_amount(self):
        self.assertEqual(assess_refund(replace(self.order, paid_minor=675), "customer-a"),
                         {"status": "full_refund_offer", "amount_minor": 675, "currency": "GBP"})

    def test_invalid_money_or_day_is_not_accepted_as_a_service_record(self):
        for field, value in [("paid_minor", 0), ("paid_minor", -1), ("paid_minor", 12.99),
                             ("paid_minor", True), ("received_day", -1), ("received_day", True)]:
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                replace(self.order, **{field: value})


if __name__ == "__main__":
    unittest.main()
