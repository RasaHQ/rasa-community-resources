"""Author controls for source normalisation, not the owner's protected acceptance."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from briefing.data import DataUnavailable, flight_payload, timeline_payload, weather_payload


def flight():
    return {"ident_iata": "DEMO101", "origin": {"code_iata": "LHR"},
            "destination": {"code_iata": "JFK"}, "scheduled_out": "2026-10-22T10:00:00Z",
            "estimated_out": None, "scheduled_in": "2026-10-22T17:00:00Z",
            "estimated_in": None, "terminal_destination": None, "status": "Scheduled"}


def weather():
    return {"timezone": "GMT", "utc_offset_seconds": 0,
            "hourly_units": {"temperature_2m": "°C", "precipitation_probability": "%", "precipitation": "mm"},
            "hourly": {"time": ["2026-10-22T17:00", "2026-10-22T18:00"],
                       "temperature_2m": [17, 16], "precipitation_probability": [20, 25], "precipitation": [0, 0.1]}}


class NormalisationControls(unittest.TestCase):
    def test_missing_estimate_terminal_and_provider_time_remain_unknown(self):
        result = flight_payload(flight())
        self.assertIsNone(result["estimated_arrival"])
        self.assertIsNone(result["terminal"])
        self.assertIsNone(result["source_timestamp"])
        self.assertEqual(result["reported_status"], "Scheduled")

    def test_times_do_not_create_a_delay_claim(self):
        record = flight(); record["estimated_in"] = "2026-10-22T19:00:00Z"
        self.assertEqual(flight_payload(record)["reported_status"], "Scheduled")

    def test_missing_required_schedule_is_unavailable(self):
        record = flight(); record["scheduled_in"] = None
        with self.assertRaises(DataUnavailable): flight_payload(record)

    def test_unqualified_timestamp_is_refused(self):
        record = flight(); record["scheduled_in"] = "2026-10-22T17:00:00"
        with self.assertRaises(DataUnavailable): flight_payload(record)

    def test_display_injection_is_refused(self):
        record = flight(); record["status"] = "<script>alert(1)</script>"
        with self.assertRaises(DataUnavailable): flight_payload(record)

    def test_hourly_values_and_arrival_marker_come_from_source(self):
        source = weather(); before = deepcopy(source)
        result = weather_payload(source, location="New York", arrival="2026-10-22T13:25:00-04:00")
        self.assertEqual(result["arrival_hour"], "2026-10-22T17:00:00+00:00")
        self.assertEqual(result["hourly"][1]["temp_c"], 16)
        self.assertEqual(source, before)

    def test_misaligned_forecast_is_refused(self):
        source = weather(); source["hourly"]["temperature_2m"].pop()
        with self.assertRaises(DataUnavailable): weather_payload(source, location="New York", arrival="2026-10-22T17:00:00Z")

    def test_wrong_units_or_nonfinite_values_are_refused(self):
        for invalid in ("unit", "nan"):
            source = weather()
            if invalid == "unit": source["hourly_units"]["temperature_2m"] = "°F"
            else: source["hourly"]["temperature_2m"][0] = float("nan")
            with self.assertRaises(DataUnavailable): weather_payload(source, location="New York", arrival="2026-10-22T17:00:00Z")

    def test_missing_arrival_hour_is_unavailable(self):
        with self.assertRaises(DataUnavailable): weather_payload(weather(), location="New York", arrival="2026-10-23T17:00:00Z")

    def test_margin_uses_timezone_and_explicit_assumption(self):
        result = timeline_payload(arrival="2026-10-22T17:00:00Z", meeting_time="2026-10-22T17:00:00-04:00", transfer_minutes=90)
        self.assertEqual(result["margin_minutes"], 150)
        self.assertEqual(result["transfer_minutes"], {"value": 90, "kind": "assumption"})
        self.assertNotIn("traffic", result)

    def test_negative_margin_is_retained(self):
        result = timeline_payload(arrival="2026-10-22T20:30:00Z", meeting_time="2026-10-22T17:00:00-04:00", transfer_minutes=90)
        self.assertEqual(result["margin_minutes"], -60)

    def test_boolean_transfer_is_refused(self):
        with self.assertRaises(DataUnavailable): timeline_payload(arrival="2026-10-22T17:00:00Z", meeting_time="2026-10-22T21:00:00Z", transfer_minutes=True)


if __name__ == "__main__": unittest.main()
