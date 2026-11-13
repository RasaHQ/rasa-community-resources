# SPDX-License-Identifier: MIT
"""The generated Banking Hub models match the example's own recorded traffic. Vendor-free."""
import copy
import importlib.util
import unittest

from pydantic import ValidationError

from bh_demo.recorded_exchanges import EXCHANGES
from decimal import Decimal
import json

from bh_demo.vendor_api import REPLY, REQUEST, dumps, loads, plain, present, reply, request_body


def exact(body):
    """A recorded body as the client reads it from the wire: numbers as Decimal, never float."""
    return json.loads(json.dumps(body), parse_float=Decimal)


class RecordedTrafficRoundTrip(unittest.TestCase):
    def test_every_recorded_body_parses_into_its_model_and_comes_back_unchanged(self):
        # The models ignore undeclared fields, so a field lost in generation would be missing here.
        for key, side, status, body in EXCHANGES:
            with self.subTest(key=key, side=side, status=status):
                model = REQUEST[key] if side == "request" else REPLY[key]
                again = plain(model.model_validate(exact(body)))
                self.assertEqual(again, exact(body))
                self.assertEqual(loads(dumps(again)), exact(body))  # and back to the same JSON numbers
        self.assertEqual(len(EXCHANGES), 8)

    def test_every_operation_has_a_request_and_a_reply_model(self):
        keys = {key for key, *_ in EXCHANGES}
        self.assertEqual(set(REQUEST), keys)
        self.assertEqual(set(REPLY), keys)


class MissingIsNotNull(unittest.TestCase):
    def test_an_optional_field_left_out_is_absent_and_null_is_refused(self):
        body = next(b for key, side, status, b in EXCHANGES if key == "party" and side == "request")
        without = copy.deepcopy(body)
        without.pop("RecCtrlIn")
        self.assertEqual(request_body("party", without), without)
        with self.assertRaises(ValidationError):
            request_body("party", {**without, "RecCtrlIn": None})

    def test_a_missing_required_field_or_wrong_type_fails(self):
        with self.assertRaises(ValidationError):
            request_body("xfer", {"XferInfo": {"CurAmt": {"Amt": "not a number"}}})

    def test_a_reply_without_an_optional_field_is_read_safely(self):
        recorded = next(b for key, side, status, b in EXCHANGES if key == "acct" and side == "response")
        changed = copy.deepcopy(recorded)
        changed["AcctRec"].pop("DepositAcctInfo", None)
        changed["AcctRec"].pop("LoanAcctInfo", None)
        record = reply("acct", changed).acct_rec
        self.assertIsNone(present(record.deposit_acct_info))


class AmountPrecision(unittest.TestCase):
    """Money is Decimal end to end: exact on both read paths and on the wire."""

    def client_with(self, reply_text):
        from bh_demo.client import BankingHubClient

        class Replay(BankingHubClient):
            def _post(self, key, body, *, write=False):
                # As the real _post does: the raw reply text parsed without floats.
                return json.loads(reply_text, parse_float=Decimal)
        return Replay.__new__(Replay)

    def recorded_reply(self, account_type):
        for (key, side, _, body), (_, _, _, answer) in zip(EXCHANGES[::2], EXCHANGES[1::2]):
            if key == "acct" and body["AcctSel"]["AcctKeys"]["AcctType"] == account_type:
                return copy.deepcopy(answer)
        raise AssertionError("no recorded " + account_type + " reply")

    def with_amount(self, account_type, raw_number):
        answer = self.recorded_reply(account_type)
        holder = (answer["AcctRec"]["DepositAcctInfo"]["AcctBal"] if account_type == "DDA"
                  else answer["AcctRec"]["LoanAcctInfo"]["NextPmt"]["PmtCompositeAmt"])
        for entry in holder:
            if entry.get("BalType") == "Avail" or entry.get("CompositeCurAmtType") == "Total":
                entry["CurAmt"]["Amt"] = "@AMOUNT@"
        # The amount goes into the reply text exactly as written, as a bank would send it.
        return json.dumps(answer).replace('"@AMOUNT@"', raw_number), answer["AcctRec"]["AcctKeys"]["AcctId"]

    def test_both_read_paths_show_each_amount_exactly(self):
        for raw, shown in (("9007199254740993", "9007199254740993.00"), ("0.1", "0.10"), ("0.2", "0.20"),
                           ("1250.07", "1250.07")):
            with self.subTest(amount=raw):
                text, account = self.with_amount("DDA", raw)
                self.assertEqual(str(self.client_with(text).available_balance(account)), shown)
                text, account = self.with_amount("LOAN", raw)
                self.assertEqual(self.client_with(text).loan_payment(account)["amount"], shown)

    def test_requests_carry_exact_numbers_on_the_wire(self):
        body = request_body("xfer", {"XferInfo": {
            "FromAcctRef": {"AcctKeys": {"AcctId": "1", "AcctType": "DDA"}},
            "ToAcctRef": {"AcctKeys": {"AcctId": "2", "AcctType": "SDA"}},
            "CurAmt": {"Amt": Decimal("0.30"), "CurCode": {"CurCodeType": "ISO4217-Alpha", "CurCodeValue": "USD"}}}})
        self.assertIsInstance(body["XferInfo"]["CurAmt"]["Amt"], Decimal)
        self.assertIn('"Amt":0.30', dumps(body))
        self.assertEqual(dumps({"Amt": Decimal("9007199254740993")}), '{"Amt":9007199254740993}')


@unittest.skipUnless(importlib.util.find_spec("datamodel_code_generator"),
                     "the models group is not installed (uv sync --group models)")
class Regeneration(unittest.TestCase):
    def test_the_committed_models_match_a_fresh_generation_from_the_pinned_archive(self):
        from bh_demo.contract import MissingContractInput, load_members
        try:
            load_members()
        except MissingContractInput as error:
            self.skipTest(str(error))
        import make_models
        self.assertEqual(make_models.main(["--check"]), 0)


if __name__ == "__main__":
    unittest.main()
