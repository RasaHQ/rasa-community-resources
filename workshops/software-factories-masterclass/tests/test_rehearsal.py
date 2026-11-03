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

class FlightWeatherGuard(unittest.TestCase):
    """The ZZ201 acceptance cases at the tool boundary: the tool, not the model, enforces the date question."""

    def weather(self, *args):
        with patch.dict(os.environ, TRAVEL_REHEARSAL="two-dates"), \
                patch.object(travel_data, "urlopen", side_effect=AssertionError("network used")):
            return travel_data.read("weather", "", "", "ZZ201", *args)

    def test_no_date_returns_no_weather_and_asks_which_date_first(self):
        result = self.weather()
        self.assertEqual(result["state"], "needs_date")
        self.assertIsNone(result["forecast"])
        self.assertNotIn("temperature_c", result)
        self.assertEqual(result["dates"], ["2026-11-03", "2026-11-04"])
        self.assertIn("which date first", result["reason"])

    def test_november_3_uses_the_estimated_arrival(self):
        result = self.weather("2026-11-03")
        self.assertEqual((result["temperature_c"], result["rain_probability_pct"]), (4, 80))
        self.assertEqual((result["arrival_basis"], result["arrival_local"]), ("estimated", "20:10 CET (Oslo)"))

    def test_november_4_uses_the_scheduled_arrival_and_says_so(self):
        result = self.weather("2026-11-04")
        self.assertEqual((result["temperature_c"], result["rain_probability_pct"]), (7, 30))
        self.assertEqual((result["arrival_basis"], result["arrival_local"]), ("scheduled", "19:20 CET (Oslo)"))

    def test_a_date_that_fits_no_record_asks_again(self):
        result = self.weather("2026-11-05")
        self.assertEqual(result["state"], "no_match")
        self.assertIsNone(result["forecast"])


if __name__ == "__main__":
    unittest.main()
