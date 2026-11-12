from pathlib import Path
import tempfile
import unittest
import zipfile

from bh_demo.contract import (
    ARCHIVE_NAME, ContractError, MEMBERS, MissingContractInput, load_members)
from tests.support import load_contract


class InputHandling(unittest.TestCase):
    """These run without any vendor bytes."""

    def test_absent_archive_is_a_plain_launch_stop(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(MissingContractInput) as raised:
                load_members(Path(folder) / ARCHIVE_NAME)
        self.assertIn("developer.fiserv.com", str(raised.exception))
        self.assertIn("resources", str(raised.exception))

    def test_wrong_bytes_fail_even_when_named_correctly(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / ARCHIVE_NAME
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr(MEMBERS["acct"][0], "not a vendor definition")
            with self.assertRaises(ContractError) as raised:
                load_members(path)
            self.assertNotIsInstance(raised.exception, MissingContractInput)

    def test_only_three_members_are_read_and_none_from_the_archive_folder(self):
        self.assertEqual(set(MEMBERS), {"party", "acct", "trn"})
        for name, _, _, _ in MEMBERS.values():
            self.assertNotIn("/archive/", name)
            self.assertTrue(name.endswith("-11.0.0-resolved.yaml"))

    def test_no_vendor_bytes_are_tracked(self):
        example = Path(__file__).resolve().parents[1]
        for path in example.rglob("*"):
            if path.is_file() and "vendor-inputs" not in path.parts and ".venv" not in path.parts \
                    and "__pycache__" not in path.parts and path.suffix in {".yaml", ".yml", ".json", ".zip"}:
                text = path.read_bytes()[:400].lower()
                if path.name in {"agent.yml", "integrations.yml"}:
                    continue
                self.assertNotIn(b"openapi", text, str(path))


class PinnedContract(unittest.TestCase):
    """These need the learner-supplied release file and skip without it."""

    @classmethod
    def setUpClass(cls):
        cls.contract = load_contract()

    def test_paths_are_the_release_paths(self):
        self.assertEqual(self.contract.path("party"), "/partyacctrel/secured")
        self.assertEqual(self.contract.path("acct"), "/accounts/secured")
        self.assertEqual(self.contract.path("trn"), "/acctTrn/secured")

    def test_one_account_document_serves_every_type(self):
        for kind in ("DDA", "SDA", "LOAN"):
            self.contract.validate_request("acct", {"AcctSel": {"AcctKeys": {"AcctId": "1", "AcctType": kind}}})

    def test_a_status_alone_is_schema_valid_so_validity_is_not_success(self):
        for key in ("party", "acct"):
            self.contract.validate_response(key, 200, {"Status": {
                "StatusCode": "0", "StatusDesc": "Success", "Severity": "Info", "SvcProviderName": "x"}})

    def test_wrong_shapes_are_refused(self):
        with self.assertRaises(ContractError):
            self.contract.validate_request("acct", {"AcctSel": {}})
        with self.assertRaises(ContractError):
            self.contract.validate_response("acct", 200, {"AcctRec": {}})
        with self.assertRaises(ContractError):
            self.contract.validate_response("party", 200, {"Status": {"Severity": "Sometimes"}})

    def test_efx_header_is_a_json_object_sent_as_a_string(self):
        header = self.contract.validate_header("acct", '{"OrganizationId":"ORG","TrnId":"t-1"}')
        self.assertEqual(header["OrganizationId"], "ORG")
        for bad in ('{"TrnId":"t-1"}', "not json", '["x"]', '{"OrganizationId":"' + "x" * 40 + '"}'):
            with self.assertRaises(ContractError):
                self.contract.validate_header("acct", bad)

    def test_the_optional_context_is_checked_against_the_release_schema(self):
        import json
        good = {"OrganizationId": "ORG", "Context": {"ClientAppName": "a" * 40, "Channel": "VOICE"}}
        for key in ("party", "acct", "trn"):
            self.contract.validate_header(key, json.dumps(good))
        malformed = [[], "context", {"ClientAppName": "a" * 41}, {"Channel": "c" * 81},
                     {"ClientAppName": 5}, {"isOverridden": "yes"}]
        for context in malformed:
            for key in ("party", "acct", "trn"):
                with self.subTest(key=key, context=context), self.assertRaises(ContractError):
                    self.contract.validate_header(key, json.dumps({"OrganizationId": "ORG", "Context": context}))

    def test_the_header_the_client_sends_passes(self):
        import json
        from bh_demo.mock import MOCK_ORGANIZATION
        header = {"OrganizationId": MOCK_ORGANIZATION, "TrnId": "0" * 36,
                  "Context": {"ClientAppName": "rasa-community-fiserv-banking-hub", "Channel": "VOICE"}}
        for key in ("party", "acct", "trn"):
            self.contract.validate_header(key, json.dumps(header))


class ReleaseDefect(unittest.TestCase):
    """Pins the vendor schema defect the README names, so the claim stays true.

    In AcctTrnService 11.0.0, BaseKeysType is a string, and AcctKeysType and
    AcctTrnKeysType are allOf that string AND an object. No value is both, so no
    history request naming an account, and no non-empty history reply, can pass.
    """

    @classmethod
    def setUpClass(cls):
        cls.contract = load_contract()

    def test_base_keys_type_is_a_string_inside_object_key_types(self):
        self.assertEqual(self.contract.schema("trn", "BaseKeysType").get("type"), "string")
        for name in ("AcctKeysType", "AcctTrnKeysType"):
            refs = [part.get("$ref") for part in self.contract.schema("trn", name)["allOf"]]
            self.assertIn("#/components/schemas/BaseKeysType", refs)

    def test_a_history_request_naming_an_account_cannot_validate(self):
        with self.assertRaises(ContractError):
            self.contract.validate_request("trn", {"AcctTrnSel": {
                "AcctKeys": {"AcctId": "5550010001", "AcctType": "DDA"}, "TrnPostType": "ExcludeMemoPost"}})

    def test_a_history_reply_with_one_row_cannot_validate(self):
        row = {"AcctTrnKeys": {"AcctTrnId": "T-1"}, "AcctTrnInfo": {"DrCrType": "Debit"},
               "AcctTrnStatus": {"AcctTrnStatusCode": "Valid"}}
        with self.assertRaises(ContractError):
            self.contract.validate_response("trn", 200, {"Status": {
                "StatusCode": "0", "StatusDesc": "Success", "Severity": "Info", "SvcProviderName": "x"},
                "RecCtrlOut": {"SentRecCount": 1}, "AcctTrnRec": [row]})


if __name__ == "__main__":
    unittest.main()
