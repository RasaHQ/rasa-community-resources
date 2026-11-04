import unittest

from display_revisions import Display, history


class DisplayRevisionTests(unittest.TestCase):
    def test_value_guard_accepts_wrong_language_on_same_schedule(self):
        result = history("value")
        self.assertFalse(result["completions"][0]["accepted"])
        accepted = result["completions"][1]
        self.assertTrue(accepted["accepted"])
        self.assertEqual(accepted["visible"]["minor"], result["canonical_minor"])
        self.assertNotEqual(accepted["visible"]["locale"], result["preferred_locale"])

    def test_locale_guard_accepts_old_money_after_amount_only_edit(self):
        state = Display()
        job = state.start()
        state.edit_amount(200050)
        self.assertTrue(state.complete(job, "locale"))
        self.assertEqual(state.visible["minor"], 100050)
        self.assertEqual(state.amount.minor, 200050)

    def test_pair_guard_rejects_both_old_jobs_and_fresh_one_progresses(self):
        result = history("pair")
        self.assertEqual([x["accepted"] for x in result["completions"]], [False, False])
        self.assertEqual(result["fresh_display"], {"minor": 200050, "currency": "EUR",
                                                  "locale": "de-DE", "text": "2.000,50"})

    def test_language_only_preserves_value_bound_approval_but_coarse_revokes_it(self):
        state = Display()
        approval = state.approve_value()
        state.change_locale("de-DE")
        self.assertTrue(state.approval_valid(approval))
        self.assertFalse(state.approval_valid(approval, coarse=True))

    def test_amount_change_invalidates_approval_even_after_changing_back(self):
        state = Display()
        approval = state.approve_value()
        state.edit_amount(200050)
        state.edit_amount(100050)
        self.assertFalse(state.approval_valid(approval))

    def test_pair_guard_refuses_locale_changed_away_and_back(self):
        state = Display()
        job = state.start()
        state.change_locale("de-DE")
        state.change_locale("en-US")
        self.assertFalse(state.complete(job, "pair"))

    def test_unsupported_locale_does_not_mutate_state(self):
        state = Display()
        with self.assertRaises(ValueError):
            state.change_locale("xx")
        self.assertEqual((state.locale, state.locale_version), ("en-US", 0))


if __name__ == "__main__":
    unittest.main()
