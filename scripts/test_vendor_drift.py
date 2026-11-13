"""Vendor-free tests for the daily drift check's download and report steps."""
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import vendor_drift as drift


class Reply(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class DriftTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        root = Path(self.folder.name)
        for patch in (mock.patch.object(drift, "ROOT", root),
                      mock.patch.object(drift, "RESULTS", root / "vendor-drift-results")):
            patch.start()
            self.addCleanup(patch.stop)

    def test_a_download_records_hashes_and_writes_only_into_vendor_inputs(self):
        result = drift.download("jack-henry-silverlake", opener=lambda request, timeout: Reply(b"zip bytes"))
        self.assertEqual(result["status"], "downloaded")
        written = Path(self.folder.name) / "examples/jack-henry-silverlake/vendor-inputs/TPG_R2026.1.00_XSD.zip"
        self.assertEqual(written.read_bytes(), b"zip bytes")

    def test_a_failed_download_is_reported_never_taken_for_no_change(self):
        def fail(request, timeout):
            raise OSError("HTTP Error 502: Bad Gateway")
        drift.download("jack-henry-symitar", opener=fail)
        self.assertEqual(drift.check("jack-henry-symitar")["status"], "download_failed")
        title, body = drift.report("jack-henry-symitar", today="13 Nov 2026")
        self.assertEqual(title, "Vendor drift: could not check jack-henry-symitar")
        self.assertIn("not a \"no change\" result", body)
        self.assertIn("502", body)

    def write(self, example, result):
        drift._write(example, result)

    def test_unchanged_files_stay_quiet(self):
        self.write("fiserv-premier-11.0.0-prm", {"status": "same", "hashes": {}})
        self.assertIsNone(drift.report("fiserv-premier-11.0.0-prm"))

    def test_compatible_and_changed_files_open_an_issue_with_a_changelog_draft(self):
        self.write("fiserv-premier-11.0.0-prm", {"status": "compatible", "tested_with": "X",
                                                  "hashes": {"vendor-inputs/a.zip": "ab" * 32}})
        title, body = drift.report("fiserv-premier-11.0.0-prm", today="13 Nov 2026")
        self.assertEqual(title, "Vendor drift: Fiserv files changed for fiserv-premier-11.0.0-prm")
        self.assertIn("everything the example uses unchanged", body)
        self.assertIn("### 13 Nov 2026: files as downloaded 13 Nov 2026", body)
        self.assertIn("ab" * 32, body)
        self.write("jack-henry-symitar", {"status": "changed", "tested_with": "X", "hashes": {},
                                          "changes": ["postTransfer request field amount changed"]})
        title, body = drift.report("jack-henry-symitar", today="13 Nov 2026")
        self.assertIn("now stops at start-up", body)
        self.assertIn("- postTransfer request field amount changed", body)

    def test_a_check_that_did_not_run_is_reported_as_could_not_check(self):
        drift.download("jack-henry-silverlake", opener=lambda request, timeout: Reply(b"zip bytes"))
        title, body = drift.report("jack-henry-silverlake", today="13 Nov 2026")  # still "downloaded"
        self.assertEqual(title, "Vendor drift: could not check jack-henry-silverlake")
        self.assertIn("compatibility check did not run", body)
        self.assertNotIn("cannot be read", body)

    def test_no_result_at_all_is_reported_as_could_not_check(self):
        title, body = drift.report("jack-henry-symitar", today="13 Nov 2026")
        self.assertEqual(title, "Vendor drift: could not check jack-henry-symitar")
        self.assertIn("no result recorded", body)

    def test_vendor_text_is_shown_literally(self):
        self.write("fiserv-premier-11.0.0-prm", {"status": "unreadable", "detail": "bad `x` <b>\n@team"})
        _, body = drift.report("fiserv-premier-11.0.0-prm", today="13 Nov 2026")
        self.assertIn("`bad 'x' <b> @team`", body)

    def test_every_example_has_a_check_and_files(self):
        self.assertEqual(set(drift.CHECKS), set(drift.EXAMPLES))
        for example in drift.EXAMPLES.values():
            for relative in example["files"].values():
                self.assertTrue(relative.startswith("vendor-inputs/"))


if __name__ == "__main__":
    unittest.main()
