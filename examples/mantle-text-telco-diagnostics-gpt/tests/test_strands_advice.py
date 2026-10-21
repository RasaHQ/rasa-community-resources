"""Constructed DTO unit controls; native tool evidence is run separately."""
import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from controls.strands_advice import ADVICE, assert_contract, run_control


def observation():
    return {"status": "network_observation", "source": {"id": "JM-N-101", "area": "north", "revision": "2026-10-11",
            "status": "degraded", "advice": ADVICE}}


class AdviceBoundaryTests(unittest.TestCase):
    def test_advice_does_not_select_and_customer_choice_executes_once(self):
        result = run_control(observation())
        assert_contract(result)
        self.assertIsNone(result["negative"]["selection"])
        self.assertEqual(len(result["positive"]["commands"]), 1)

    def test_same_contract_catches_misclassified_advice(self):
        result = run_control(observation(), mutant=True)
        self.assertEqual(result["negative"]["result"]["status"], "selected")
        with self.assertRaisesRegex(AssertionError, "Specialist advice must not select"):
            assert_contract(result)

    def test_mutation_cannot_change_the_observation_or_next_control(self):
        record = observation()
        before = copy.deepcopy(record)
        run_control(record, mutant=True)
        self.assertEqual(record, before)
        assert_contract(run_control(record))

    def test_unavailable_or_action_bearing_observation_is_refused(self):
        record = observation()
        record["source"]["action"] = "factory_reset"
        for value in [record, {"status": "network_evidence_unavailable"}]:
            with self.assertRaises(ValueError):
                run_control(value)


if __name__ == "__main__":
    unittest.main()
