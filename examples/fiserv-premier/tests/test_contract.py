from pathlib import Path
import tempfile
import unittest
import zipfile

from premier_demo.contract import (
    ARCHIVE_NAME, ContractError, MissingContractInput, PremierContract, load_members)
from tests.support import load_contract


class InputHandling(unittest.TestCase):
    """These run without any vendor bytes."""

    def test_absent_archive_is_a_plain_launch_stop(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(MissingContractInput) as raised:
                load_members(Path(folder) / ARCHIVE_NAME)
        self.assertIn("developer.fiserv.com", str(raised.exception))

    def test_wrong_bytes_fail_even_when_named_correctly(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / ARCHIVE_NAME
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("banking-hub//Premier/x.yaml", "openapi: 3.0.1")
            with self.assertRaises(ContractError) as raised:
                load_members(path)
            self.assertNotIsInstance(raised.exception, MissingContractInput)

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
    @classmethod
    def setUpClass(cls):
        cls.contract = load_contract()

    def test_dda_and_loan_are_distinct_documents_on_one_path(self):
        self.assertEqual(self.contract.path("dda"), self.contract.path("loan"))
        loan = {"AcctSel": {"AcctKeys": {"AcctId": "1", "AcctType": "LOAN"}}}
        dda = {"AcctSel": {"AcctKeys": {"AcctId": "1", "AcctType": "DDA"}}}
        self.contract.validate_request("loan", loan)
        self.contract.validate_request("dda", dda)
        with self.assertRaises(ContractError):
            self.contract.validate_request("dda", loan)
        with self.assertRaises(ContractError):
            self.contract.validate_request("loan", dda)

    def test_account_document_is_selected_from_a_declared_key(self):
        self.assertEqual(self.contract.document_for_account("DDA"), "dda")
        self.assertEqual(self.contract.document_for_account("LOAN"), "loan")
        with self.assertRaises(ContractError):
            self.contract.document_for_account(None)

    def test_wrong_shapes_are_refused(self):
        with self.assertRaises(ContractError):
            self.contract.validate_request("xfer", {"XferInfo": {"TransferType": "Bogus"}})
        with self.assertRaises(ContractError):
            self.contract.validate_request("trn", {"AcctTrnSel": {"AcctKeys": {"AcctId": 5}}})
        with self.assertRaises(ContractError):
            self.contract.validate_response("dda", 200, {"AcctRec": {}})

    def test_efx_header_is_a_json_object_sent_as_a_string(self):
        header = self.contract.validate_header("dda", '{"OrganizationId":"ORG","TrnId":"t-1"}')
        self.assertEqual(header["OrganizationId"], "ORG")
        for bad in ('{"TrnId":"t-1"}', "not json", '["x"]', '{"OrganizationId":"' + "x" * 40 + '"}'):
            with self.assertRaises(ContractError):
                self.contract.validate_header("dda", bad)


if __name__ == "__main__":
    unittest.main()
