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


class VendorVersions(unittest.TestCase):
    """A newer Fiserv download starts the example only if nothing it uses changed."""

    @classmethod
    def setUpClass(cls):
        load_contract()  # skips without the learner-supplied archive
        from premier_demo.contract import default_path
        cls.source = default_path()

    def rebuilt(self, folder, edit_member=None, drop=None):
        """A copy of the pinned archive with one member edited or removed."""
        import yaml
        from premier_demo.contract import MEMBERS
        names = {key: name for key, (name, _, _, _) in MEMBERS.items()}
        target = Path(folder) / ARCHIVE_NAME
        with zipfile.ZipFile(self.source) as old, zipfile.ZipFile(target, "w") as new:
            for info in old.infolist():
                data = old.read(info)
                if drop and info.filename == names[drop]:
                    continue
                if edit_member and info.filename == names[edit_member[0]]:
                    if edit_member[1] is None:
                        data += b"\n"
                    elif getattr(edit_member[1], "__name__", "") == "apply":
                        data = edit_member[1](data)  # bytes -> bytes
                    else:
                        document = yaml.safe_load(data)
                        edit_member[1](document)
                        data = yaml.safe_dump(document).encode()
                new.writestr(info, data)
        return target

    @staticmethod
    def _resolve(document, node):
        while isinstance(node, dict) and "$ref" in node:
            target = document
            for part in node["$ref"][2:].split("/"):
                target = target[part.replace("~1", "/").replace("~0", "~")]
            node = target
        return node

    def _post(self, document, key):
        from premier_demo.contract import MEMBERS
        return document["paths"][MEMBERS[key][3]]["post"]

    def test_a_newer_archive_that_changes_nothing_used_loads_and_says_so(self):
        with tempfile.TemporaryDirectory() as folder:
            contract = PremierContract.from_path(self.rebuilt(folder, edit_member=("loan", None)))
        self.assertTrue(contract.newer_archive)
        self.assertEqual(contract.newer_files, ("loan",))
        pinned = PremierContract.from_path()
        self.assertEqual((pinned.newer_archive, pinned.newer_files), (False, ()))

    def test_a_change_to_anything_used_stops_and_names_it(self):
        from premier_demo.contract import VendorChanged

        def xfer_status_type(document):
            ok = self._post(document, "xfer")["responses"]["201"]["content"]["application/json"]["schema"]
            body = self._resolve(document, ok)
            rec = self._resolve(document, body["properties"]["XferStatusRec"])
            status = self._resolve(document, rec["properties"]["XferStatus"])
            self._resolve(document, status["properties"]["XferStatusCode"])["type"] = "integer"

        def dda_new_required(document):
            body = self._resolve(document, self._post(document, "dda")["requestBody"]["content"]["application/json"]["schema"])
            body["required"] = sorted(set(body.get("required", [])) | {"NewRequiredField"})

        cases = ((("xfer", xfer_status_type), None,
                  "XferAddOper (xfer) response field XferStatusRec.XferStatus.XferStatusCode changed"),
                 (("dda", dda_new_required), None, "getAccountsSecured (dda) now requires different request fields"),
                 (None, "trn", "AcctTrnService-11.0.0_PRM-Inq_DDA.yaml is no longer in the archive"))
        for edit, drop, expected in cases:
            with self.subTest(expected=expected), tempfile.TemporaryDirectory() as folder:
                with self.assertRaises(VendorChanged) as raised:
                    PremierContract.from_path(self.rebuilt(folder, edit_member=edit, drop=drop))
                self.assertIn(expected, raised.exception.changes)

    def _acct_id_holder(self, document):
        """The properties object that holds AcctSel.AcctKeys.AcctId in the DDA request."""
        node = self._resolve(document, self._post(document, "dda")["requestBody"]["content"]["application/json"]["schema"])
        for name in ("AcctSel", "AcctKeys"):
            node = self._resolve(document, node["properties"][name])
        return node["properties"]

    def _edit_yaml(self, edit):
        import yaml

        def apply(data):
            document = yaml.safe_load(data)
            edit(document)
            return yaml.safe_dump(document).encode()
        return apply

    def test_any_validation_keyword_on_a_used_field_counts_and_documentation_does_not(self):
        from premier_demo.contract import VendorChanged

        def max_length(document):
            holder = self._acct_id_holder(document)
            holder["AcctId"] = {"allOf": [holder["AcctId"]], "maxLength": 1}

        def reworded(document):
            holder = self._acct_id_holder(document)
            target = self._resolve(document, holder["AcctId"])
            target["description"] = "Reworded by the vendor."

        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(VendorChanged) as raised:
                PremierContract.from_path(self.rebuilt(folder, edit_member=("dda", self._edit_yaml(max_length))))
            self.assertIn("getAccountsSecured (dda) request field AcctSel.AcctKeys.AcctId changed",
                          raised.exception.changes)
        with tempfile.TemporaryDirectory() as folder:
            contract = PremierContract.from_path(self.rebuilt(folder, edit_member=("dda", self._edit_yaml(reworded))))
            self.assertEqual(contract.newer_files, ("dda",))

    def test_reference_cycles_are_refused_with_a_clear_reason_not_a_hang(self):
        def self_cycle(document):
            document["components"]["schemas"]["Loop"] = {"$ref": "#/components/schemas/Loop"}
            self._acct_id_holder(document)["AcctId"] = {"$ref": "#/components/schemas/Loop"}

        def mutual_cycle(document):
            document["components"]["schemas"]["LoopA"] = {"$ref": "#/components/schemas/LoopB"}
            document["components"]["schemas"]["LoopB"] = {"$ref": "#/components/schemas/LoopA"}
            self._acct_id_holder(document)["AcctId"] = {"$ref": "#/components/schemas/LoopA"}

        for edit in (self_cycle, mutual_cycle):
            with self.subTest(edit=edit.__name__), tempfile.TemporaryDirectory() as folder:
                with self.assertRaisesRegex(ContractError, "schema_reference_cycle"):
                    PremierContract.from_path(self.rebuilt(folder, edit_member=("dda", self._edit_yaml(edit))))

    def test_the_recorded_surface_is_exactly_the_pinned_files(self):
        import yaml
        from premier_demo.contract import USED_SURFACE_SHA256, surface_digest, used_surface
        from premier_demo.used_surface_expected import EXPECTED
        surface = used_surface({key: yaml.safe_load(raw) for key, raw in load_members().items()})
        self.assertEqual(surface, EXPECTED)
        self.assertEqual(surface_digest(surface), USED_SURFACE_SHA256)
