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
        self.assertEqual((first["local_date"], first["estimated_arrival_local"], first["scheduled_arrival_local"]),
                         ("2026-11-03", "20:10 CET (Oslo)", "19:20 CET (Oslo)"))
        self.assertEqual((second["local_date"], second["scheduled_arrival_local"], second["estimated_arrival_local"]),
                         ("2026-11-04", "19:20 CET (Oslo)", None))
