"""Source exclusion controls use authored bytes, never actual vendor definitions."""
import hashlib
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import check_vendor_definitions as gate


class VendorDefinitionGateTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.git("init", "-q")

    def git(self, *args):
        return subprocess.run(["git", *args], cwd=self.root, check=True,
                              capture_output=True).stdout

    def stage(self, name, data, force=False):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        self.git("add", *( ["-f"] if force else [] ), "--", name)
        return path

    def test_authored_payloads_and_normal_rasa_config_are_allowed(self):
        self.stage("examples/jack-henry-symitar/fixtures/response.json",
                   b'{"balance":"10.00","alias":"fictional-checking"}')
        self.stage("examples/jack-henry-silverlake/agent.yml", b"name: fictional\nskills: []\n")
        self.assertEqual(gate.findings(self.root), [])

    def test_force_added_ignored_inputs_are_rejected_for_all_examples(self):
        self.stage(".gitignore", b"vendor-inputs/\n")
        names = ["examples/" + vendor + "/vendor-inputs/definition" for vendor in
                 ("jack-henry-symitar", "jack-henry-silverlake", "fiserv-premier-11.0.0-prm")]
        for name in names:
            self.stage(name, b"authored placeholder", force=True)
        self.assertEqual({p for p, _ in gate.findings(self.root)}, set(names))

    def test_ignored_manual_inputs_are_not_read_or_qualified(self):
        self.stage(".gitignore", b"vendor-inputs/\n")
        path = self.root / "examples/jack-henry-symitar/vendor-inputs/accounts/accounts.yaml"
        path.parent.mkdir(parents=True)
        path.write_bytes(b"untracked manual placeholder")
        self.assertEqual(gate.findings(self.root), [])

    def test_out_of_path_schema_and_generated_schema_fixtures_are_rejected(self):
        samples = {
            "openapi.yaml": b"openapi: 3.0.1\ninfo: {}\npaths: {}\n",
            "spec.txt": b'{"openapi":"3.0.1","paths":{}}',
            "derived.json": b'{"$schema":"https://example.invalid/schema","type":"object"}',
            "fixture.wsdl": b'<wsdl:definitions xmlns:wsdl="urn:fictional"/>',
            "fixture.xml": b'<xs:schema xmlns:xs="urn:fictional"/>',
        }
        for name, raw in samples.items():
            self.stage("examples/jack-henry-symitar/fixtures/" + name, raw)
        self.assertEqual(len(gate.findings(self.root)), len(samples))

    def test_index_blob_cannot_be_hidden_by_clean_worktree_contents(self):
        path = self.stage("examples/jack-henry-silverlake/fixtures/hidden.txt",
                          b'<definitions xmlns="urn:fictional"/>')
        path.write_bytes(b"innocent unstaged replacement")
        self.assertEqual(len(gate.findings(self.root)), 1)

    def test_pinned_artifact_hash_is_rejected_without_schema_markers(self):
        raw = b"authored bytes standing in for a pinned artifact"
        self.stage("examples/fiserv-premier-11.0.0-prm/fixtures/unmarked.dat", raw)
        with patch.object(gate, "BANNED_HASHES", {hashlib.sha256(raw).hexdigest()}):
            self.assertEqual(gate.findings(self.root)[0][1], "pinned vendor artifact")

    def test_archives_are_reported_without_dumping_contents(self):
        self.stage("examples/jack-henry-symitar/fixtures/archive.bin", b"PK\x03\x04fictional")
        self.assertEqual(gate.findings(self.root)[0][1], "tracked archive requires source review")


if __name__ == "__main__":
    unittest.main()
