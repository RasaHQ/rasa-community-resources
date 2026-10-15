"""Qualify the reduced recorded traces separately from synthetic controls."""
import hashlib
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import replay


RECORDINGS = ROOT / "receipts" / "recorded-pair-20261013"


class RecordedPair(unittest.TestCase):
    def test_reduced_files_match_recorded_hashes_and_keep_acquisition_status(self):
        receipt = json.loads((RECORDINGS / "receipt.json").read_text())
        self.assertEqual(receipt["acquisitionDate"], "2026-10-13")
        self.assertEqual({r["variant"] for r in receipt["results"]}, {"bare", "referenced"})
        for result in receipt["results"]:
            with self.subTest(variant=result["variant"]):
                data = (RECORDINGS / result["derivedFile"]).read_bytes()
                self.assertEqual(hashlib.sha256(data).hexdigest(), result["derivedSha256"])
                saved = json.loads(data)
                self.assertEqual(saved["status"], "incomplete")
                self.assertEqual(saved["variant"], result["variant"])
                self.assertEqual(len(saved["turns"]), 2)
                self.assertEqual(replay.validate_episode(saved["turns"]), result["readerResult"])

    def test_both_recordings_pass_tool_path_without_closing_the_original_task(self):
        for variant in ("bare", "referenced"):
            with self.subTest(variant=variant):
                saved = json.loads((RECORDINGS / (variant + ".json")).read_text())
                result = replay.validate_episode(saved["turns"])
                self.assertEqual(result["status"], "passed")
                self.assertEqual(result["tool_order"], ["request_change", "record_demo_handoff"])
                self.assertIs(result["task_closed"], False)
                self.assertIn("blocked_request", {f["skill_id"] for f in result["terminal_frames"]})


if __name__ == "__main__":
    unittest.main()
