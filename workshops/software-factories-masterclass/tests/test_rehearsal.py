import os
import unittest
from unittest.mock import patch
import travel_data

class Rehearsal(unittest.TestCase):
    @patch.dict(os.environ, TRAVEL_REHEARSAL="two-dates")
    @patch.object(travel_data, "urlopen", side_effect=AssertionError("network used"))
    def test_arrivals_and_forecasts(self, network):
        status = travel_data.read("status", "ZZ201")
        self.assertEqual(status["source"], "Classroom fixture")
        first, second = status["records"]
        self.assertIsNone(second["estimated_arrival"])
        for stamp, expected in [(first["scheduled_arrival"], 8), (first["estimated_arrival"], 4),
                                (second["scheduled_arrival"], 7)]:
            self.assertEqual(travel_data.read("weather", "BGO", stamp)["temperature_c"], expected)
        self.assertEqual(travel_data.read("fx", "USD", "GBP", 100)["state"], "unavailable")

    @patch.dict(os.environ, TRAVEL_REHEARSAL="two-dates")
    @patch.object(travel_data, "urlopen", side_effect=AssertionError("network used"))
    def test_two_date_case_gives_bergen_clock_times(self, network):
        first, second = travel_data.read("status", "ZZ201")["records"]
        self.assertEqual((first["estimated_arrival_local"], first["estimated_arrival_local_date"],
                          first["scheduled_arrival_local"], first["scheduled_arrival_local_date"]),
                         ("20:10 CET (Oslo)", "2026-11-03", "19:20 CET (Oslo)", "2026-11-03"))
        self.assertEqual((second["scheduled_arrival_local"], second["scheduled_arrival_local_date"],
                          second["estimated_arrival_local"], second["estimated_arrival_local_date"]),
                         ("19:20 CET (Oslo)", "2026-11-04", None, None))
        self.assertIn("wait for the answer before any weather lookup", travel_data.read("status", "ZZ201")["next_step"])
