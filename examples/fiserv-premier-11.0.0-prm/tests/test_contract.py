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

    def test_the_recorded_exchanges_are_valid_on_the_pinned_archive_and_cover_every_document(self):
        from premier_demo.contract import MEMBERS
        from premier_demo.recorded_exchanges import EXCHANGES
        self.assertEqual(PremierContract.from_path().exchange_problems(), [])
        for side in ("header", "request", "response"):
            self.assertEqual({key for key, kind, *_ in EXCHANGES if kind == side}, set(MEMBERS))

    def _acct_id_holder(self, document):
        """The properties object that holds AcctSel.AcctKeys.AcctId in the DDA request."""
        node = self._request_root(document, "dda")
        for name in ("AcctSel", "AcctKeys"):
            node = self._resolve(document, node["properties"][name])
        return node["properties"]

    def _request_root(self, document, key):
        return self._resolve(document, self._post(document, key)["requestBody"]["content"]["application/json"]["schema"])

    def _reply_root(self, document, key, status="200"):
        return self._resolve(document, self._post(document, key)["responses"][status]["content"]["application/json"]["schema"])

    def _edit_yaml(self, edit):
        import yaml

        def apply(data):
            document = yaml.safe_load(data)
            edit(document)
            return yaml.safe_dump(document).encode()
        return apply

    def assert_stops(self, key, edit, prefix):
        from premier_demo.contract import VendorChanged
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(VendorChanged) as raised:
                PremierContract.from_path(self.rebuilt(folder, edit_member=(key, self._edit_yaml(edit))))
        self.assertTrue(any(change.startswith(prefix) for change in raised.exception.changes),
                        raised.exception.changes)

    def assert_loads(self, key, edit):
        with tempfile.TemporaryDirectory() as folder:
            contract = PremierContract.from_path(self.rebuilt(folder, edit_member=(key, self._edit_yaml(edit))))
        self.assertEqual(contract.newer_files, (key,))

    def _xfer_status_code(self, document):
        record = self._resolve(document, self._reply_root(document, "xfer", "201")["properties"]["XferStatusRec"])
        status = self._resolve(document, record["properties"]["XferStatus"])
        return self._resolve(document, status["properties"]["XferStatusCode"])

    def test_a_change_the_recorded_traffic_no_longer_fits_stops_and_names_it(self):
        from premier_demo.contract import VendorChanged

        def xfer_status_type(document):
            self._xfer_status_code(document)["type"] = "integer"

        def dda_new_required(document):
            body = self._request_root(document, "dda")
            body["required"] = sorted(set(body.get("required", [])) | {"NewRequiredField"})

        def acct_id_max_length_in_all_of(document):
            holder = self._acct_id_holder(document)
            holder["AcctId"] = {"allOf": [holder["AcctId"]], "maxLength": 1}

        def fewer_balances(document):
            record = self._resolve(document, self._reply_root(document, "dda")["properties"]["AcctRec"])
            info = self._resolve(document, record["properties"]["DepositAcctInfo"])
            self._resolve(document, info["properties"]["AcctBal"])["maxItems"] = 0

        def operation_renamed(document):
            self._post(document, "xfer")["operationId"] = "XferAddOperV2"

        cases = (("xfer", xfer_status_type, "XferAddOper (xfer) 201 response is no longer valid at XferStatusRec/XferStatus/XferStatusCode"),
                 ("dda", dda_new_required, "getAccountsSecured (dda) request is no longer valid at the whole body"),
                 ("dda", acct_id_max_length_in_all_of, "getAccountsSecured (dda) request is no longer valid at AcctSel/AcctKeys/AcctId"),
                 ("dda", fewer_balances, "getAccountsSecured (dda) 200 response is no longer valid at AcctRec/DepositAcctInfo/AcctBal"),
                 ("xfer", operation_renamed, "XferAddOper (xfer) is no longer at /xferservice/payments/transfers"))
        for key, edit, prefix in cases:
            with self.subTest(edit=edit.__name__):
                self.assert_stops(key, edit, prefix)
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(VendorChanged) as raised:
                PremierContract.from_path(self.rebuilt(folder, drop="trn"))
            self.assertIn("AcctTrnService-11.0.0_PRM-Inq_DDA.yaml is no longer in the archive", raised.exception.changes)

    def test_a_required_field_added_inside_oneof_or_anyof_branches_stops(self):
        def one_of(document):
            self._request_root(document, "dda")["oneOf"] = [{"required": ["NewRequiredField"]},
                                                            {"required": ["OtherNewField"]}]

        def any_of(document):
            self._request_root(document, "xfer")["anyOf"] = [{"required": ["NewRequiredField"]},
                                                             {"required": ["OtherNewField"]}]

        self.assert_stops("dda", one_of, "getAccountsSecured (dda) request is no longer valid")
        self.assert_stops("xfer", any_of, "XferAddOper (xfer) request is no longer valid")

    def test_a_rule_on_the_request_root_or_a_nested_object_stops_even_inside_allof(self):
        def root_direct(document):
            self._request_root(document, "dda")["maxProperties"] = 0

        def root_composed(document):
            self._request_root(document, "dda")["allOf"] = [{"maxProperties": 0}]  # original keys kept

        def nested_composed(document):
            properties = self._request_root(document, "dda")["properties"]
            properties["AcctSel"] = {"allOf": [properties["AcctSel"], {"maxProperties": 0}]}

        for edit, where in ((root_direct, "the whole body"), (root_composed, "the whole body"),
                            (nested_composed, "AcctSel")):
            with self.subTest(edit=edit.__name__):
                self.assert_stops("dda", edit, "getAccountsSecured (dda) request is no longer valid at " + where)

    def test_a_narrowed_enum_on_a_value_the_example_reads_stops(self):
        def narrow(document):
            code = self._xfer_status_code(document)
            code["enum"] = [value for value in code.get("enum", []) if value != "Valid"] or ["Rejected"]

        self.assert_stops("xfer", narrow, "XferAddOper (xfer) 201 response is no longer valid at XferStatusRec/XferStatus/XferStatusCode")

    def test_documentation_changes_and_a_new_optional_field_still_load(self):
        def reworded(document):
            self._resolve(document, self._acct_id_holder(document)["AcctId"])["description"] = "Reworded by the vendor."

        def new_sibling(document):
            record = self._resolve(document, self._reply_root(document, "dda")["properties"]["AcctRec"])
            self._resolve(document, record["properties"]["DepositAcctInfo"])["properties"]["NewOptionalField"] = {"type": "string"}

        self.assert_loads("dda", reworded)
        self.assert_loads("dda", new_sibling)

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

    def test_a_validator_that_cannot_run_is_could_not_check_never_compatible(self):
        from unittest import mock
        with tempfile.TemporaryDirectory() as folder:
            archive = self.rebuilt(folder, edit_member=("loan", None))
            with mock.patch("premier_demo.contract.best_match", side_effect=RuntimeError("validator broke")):
                with self.assertRaisesRegex(ContractError, "could_not_check"):
                    PremierContract.from_path(archive)
