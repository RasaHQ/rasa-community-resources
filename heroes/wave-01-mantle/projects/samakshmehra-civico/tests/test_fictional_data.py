"""Data-contract checks for the entirely fictional public demo."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib import directory  # noqa: E402


def seed(name: str):
    return json.loads((ROOT / "data" / name).read_text(encoding="utf-8"))


class TestFictionalData(unittest.TestCase):
    def test_dummy_pins_remain_strings_with_leading_zeros(self):
        for row in seed("wards.json")["wards"]:
            with self.subTest(locality=row["locality"]):
                pin = row["pincode"]
                self.assertIsInstance(pin, str)
                self.assertRegex(pin, r"^000[0-9]{3}$")
                self.assertEqual(directory.extract_pincode(pin), pin)
                spoken = " ".join(
                    ("zero", "one", "two", "three", "four", "five", "six",
                     "seven", "eight", "nine")[int(digit)] for digit in pin
                )
                self.assertEqual(directory.extract_pincode(spoken), pin)

    def test_every_fictional_locality_and_alias_still_routes_to_its_ward(self):
        rows = seed("wards.json")["wards"]
        self.assertEqual(len({row["locality"] for row in rows}), len(rows))
        for row in rows:
            for name in [row["locality"], *row.get("aliases", [])]:
                with self.subTest(locality=row["locality"], spoken=name):
                    matches = directory.find_ward(name)["matches"]
                    self.assertIn(row["ward_id"], [m["ward_id"] for m in matches])

    def test_seeded_complaints_link_to_the_fictional_caller_and_directory(self):
        callers = {c["citizen_id"]: c for c in seed("citizens.json")}
        localities = {w["locality"]: w for w in seed("wards.json")["wards"]}
        categories = seed("routing.json")["categories"]
        complaints = seed("complaints.json")["complaints"]
        self.assertEqual(len({c["complaint_id"] for c in complaints}), len(complaints))
        for complaint in complaints:
            with self.subTest(complaint=complaint["complaint_id"]):
                self.assertEqual(complaint["phone"],
                                 callers[complaint["citizen_id"]]["phone"])
                self.assertEqual(complaint["ward_id"],
                                 localities[complaint["locality"]]["ward_id"])
                self.assertEqual(complaint["department"],
                                 categories[complaint["category"]]["department"])

    def test_caller_and_helpdesk_identifiers_are_non_dialable_placeholders(self):
        for caller in seed("citizens.json"):
            with self.subTest(caller=caller["citizen_id"]):
                self.assertTrue(caller["name"].startswith("Demo Caller "))
                self.assertRegex(caller["phone"], r"^0000000[0-9]{3}$")
                self.assertEqual(directory.extract_phone(caller["phone"]), caller["phone"])
        wards = seed("wards.json")
        contacts = [wards["helpline"], wards["general_cell"]["officer_contact"]]
        contacts.extend(row["officer_contact"] for row in wards["wards"])
        contacts.extend(level["contact"] for level in seed("escalation.json")["levels"])
        for contact in contacts:
            with self.subTest(contact=contact):
                self.assertRegex(contact, r"^0000-000-0[0-9]{3}$")


if __name__ == "__main__":
    unittest.main()
