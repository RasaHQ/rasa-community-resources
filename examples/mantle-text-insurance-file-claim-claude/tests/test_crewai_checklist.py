"""Service/protocol controls only. Constructed DTOs are not native CrewAI proof."""
import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from controls.crewai_checklist import advice_text, assert_contract, run_scenario  # noqa: E402
from crew_transport import SOURCES  # noqa: E402


def protocol_record():
    source = copy.deepcopy(SOURCES["vehicle"])
    return {"status": "ready", "source": source, "checklist": {"claim_type": "vehicle", "documents": source["required_documents"]}}


class CrewAdviceBoundaryTests(unittest.TestCase):
    def test_actual_service_preserves_unknown_and_missing_state_contract(self):
        rows = [run_scenario(protocol_record(), state) for state in ("processing", "received", "not_provided")]
        assert_contract(rows)
        self.assertIn("Incident details, Repair estimate", rows[0]["advice_text"])
        self.assertEqual(rows[0]["service_requirements"], ["damage_photos", "repair_estimate"])

    def test_same_contract_detects_crew_checklist_authority_mutation(self):
        rows = [run_scenario(protocol_record(), state, mutant=True) for state in ("processing", "received", "not_provided")]
        self.assertEqual(rows[0]["submission"]["status"], "pending")
        self.assertEqual(rows[0]["reconciled"]["status"], "acknowledged")
        self.assertEqual(rows[0]["submission_count"], 1)
        with self.assertRaisesRegex(AssertionError, "Processing damage photo must block"):
            assert_contract(rows)

    def test_incomplete_or_modified_advice_is_not_presented_as_checked(self):
        bad = protocol_record()
        bad["checklist"]["documents"].append("Invented item")
        for value in ({"status": "incomplete"}, bad):
            with self.assertRaises(ValueError):
                advice_text(value)

    def test_mutation_is_scoped_and_cannot_contaminate_next_control(self):
        run_scenario(protocol_record(), "processing", mutant=True)
        row = run_scenario(protocol_record(), "processing")
        self.assertEqual(row["submission"]["status"], "blocked")
        self.assertEqual(row["submission_count"], 0)


if __name__ == "__main__":
    unittest.main()
