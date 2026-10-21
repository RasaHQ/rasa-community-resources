"""Addendum to accept_contract.py (b2ad9a21, unchanged): S5e. A bare string for replaces is refused, never read letter by letter."""
import unittest

import accept_contract as base
import zeo_core.contracts.ui.widgets as w


class S5e(unittest.TestCase):
    def test_a_bare_string_for_replaces_is_refused_before_any_state_change(self):
        board = w.WidgetBoard(); board.begin_request("r1")
        board.apply(base.event("r1", "weather", "weather_hourly", "d-wx", 1), w.DataRef.model_validate(base.weather()))
        with self.assertRaises(w.WidgetRefused):
            board.begin_request("r2", replaces="weather")
        self.assertEqual(board.cards()["weather"].id, "d-wx")

    def test_the_old_request_cannot_write_the_replaced_widget_after_a_list_replace(self):
        board = w.WidgetBoard(); board.begin_request("r1")
        board.begin_request("r2", replaces=["weather"])
        with self.assertRaises(w.WidgetRefused):
            board.apply(base.event("r1", "weather", "weather_hourly", "d-wx", 1), w.DataRef.model_validate(base.weather()))


if __name__ == "__main__":
    unittest.main()
