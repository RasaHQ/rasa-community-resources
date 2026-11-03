import importlib.util
import json
import unittest
import tempfile
from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import patch
import travel_data as travel
from factory import build

NOW=datetime(2026,11,2,18,30,tzinfo=timezone.utc)
def xml_board(code, direction):
    other="BGO" if code=="OSL" else "OSL"
    root=travel.ET.Element("airport",name=code)
    rows=travel.ET.SubElement(root,"flights",lastUpdate=NOW.isoformat())
    for clock in ["17:00","19:00","23:30"]:
        leg=travel.ET.SubElement(rows,"flight")
        for k,v in {"airport":other,"arr_dep":direction,"flight_id":"SK123","schedule_time":"2026-11-02T"+clock+":00Z"}.items():
            travel.ET.SubElement(leg,k).text=v
    return root

class LocalClock(unittest.TestCase):
    def test_november_utc_becomes_the_airport_clock_time(self):
        from zoneinfo import ZoneInfo
        oslo = ZoneInfo("Europe/Oslo")
        self.assertEqual(travel.local_clock("2026-11-03T17:25:00Z", oslo), "18:25 CET (Oslo)")
        self.assertEqual(travel.local_clock("2026-07-03T17:25:00Z", oslo), "19:25 CEST (Oslo)")
        self.assertIsNone(travel.local_clock(None, oslo))


class Readers(unittest.TestCase):
    def test_evening_in_origin_zone(self):
        result=travel.read("flights","OSL","BGO",now=NOW,request=lambda u,p:xml_board(p["airport"],p["direction"]))
        self.assertEqual([f["scheduled_departure"] for f in result["records"]],["2026-11-02T19:00:00Z"])
        self.assertEqual([f["scheduled_departure_local"] for f in result["records"]],["20:00 CET (Oslo)"])
        self.assertIn("_local", result["times_note"])
    def test_unsupported_route(self):
        self.assertEqual(travel.read("flights","JFK","LHR")["state"],"unavailable")

    def test_timeout(self):
        def broken(*a):
            raise TimeoutError("secret")

        result = travel.read("weather", "LHR", request=broken)
        self.assertEqual(result["state"], "unavailable")
        self.assertNotIn("secret", str(result))

    def test_fx(self):
        data = {"base": "USD", "quote": "GBP", "rate": 0.75, "date": "2026-10-30"}
        result = travel.read("fx", "USD", "GBP", "200", request=lambda *a: data)
        self.assertEqual(
            (result["converted"], result["reference_date"]), (150, "2026-10-30")
        )

    def test_arrival_weather(self):
        h = {
            "time": [int(NOW.timestamp()) - 1800],
            "temperature_2m": [10],
            "precipitation_probability": [25],
        }
        result = travel.read(
            "weather", "LHR", NOW.isoformat(), request=lambda *args: {"hourly": h}
        )
        self.assertEqual(result["temperature_c"], 10)
        self.assertIn("18:00:00", result["forecast_hour_local"])

    def test_unknown_airport_and_out_of_window(self):
        self.assertEqual(travel.read("weather", "ZZZ")["state"], "unavailable")
        self.assertEqual(
            travel.read("weather", "LHR", request=lambda *a: {"hourly": {"time": []}})[
                "state"
            ],
            "unavailable",
        )

    def test_status_filters_number(self):
        res=travel.read("status","SK123",request=lambda u,p:xml_board(p["airport"],p["direction"]))
        self.assertEqual(res["records"][0]["flight"],"SK123")
        self.assertTrue(res["records"][0]["scheduled_arrival"])



class Factory(unittest.TestCase):
    def test_full_agent(self):
        with tempfile.TemporaryDirectory() as d:
            project = Path(d) / "new"
            raw = (build.ROOT / "reference/full.json").read_bytes()
            build.generate(raw, project)
            s = (project / "skills/travel_briefing/skill.md").read_text()
            code = (project / "skills/travel_briefing/tools.py").read_text()
            for name, *_ in build.TOOLS.values():
                self.assertIn("@tool." + name, s)
                self.assertIn("async def " + name + "(", code)
            with self.assertRaises(ValueError):
                build.generate(raw, project)

    def test_disallowed_tool(self):
        spec = json.loads((build.ROOT / "reference/full.json").read_text())
        spec["tools"].append("purchase_ticket")
        with self.assertRaises(ValueError):
            build.validate(json.dumps(spec).encode())
