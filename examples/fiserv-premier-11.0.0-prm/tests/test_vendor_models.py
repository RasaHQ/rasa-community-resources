# SPDX-License-Identifier: MIT
"""The generated Premier models match the example's own recorded traffic. Vendor-free."""
import copy
import importlib.util
import unittest

from pydantic import ValidationError

from premier_demo.recorded_exchanges import EXCHANGES
from decimal import Decimal
import json

from premier_demo.vendor_api import REPLY, REQUEST, dumps, loads, plain, reply, request_body


def exact(body):
    """A recorded body as the client reads it from the wire: numbers as Decimal, never float."""
    return json.loads(json.dumps(body), parse_float=Decimal)


class RecordedTrafficRoundTrip(unittest.TestCase):
    def test_every_recorded_body_parses_into_its_model_and_comes_back_unchanged(self):
        # A field lost in generation would be missing from the dump, so this is the real guard:
        # the models ignore undeclared fields rather than keep them.
        checked = 0
        for key, side, status, body in EXCHANGES:
            if side == "header":  # EFXHeader is a JSON string header, checked by contract.py
                continue
            with self.subTest(key=key, side=side, status=status):
                model = REQUEST[key] if side == "request" else REPLY[key]
                again = plain(model.model_validate(exact(body)))
                self.assertEqual(again, exact(body))
                self.assertEqual(loads(dumps(again)), exact(body))  # and back to the same JSON numbers
                checked += 1
        self.assertEqual(checked, 14)

    def test_every_document_has_a_request_and_a_reply_model(self):
        keys = {key for key, *_ in EXCHANGES}
        self.assertEqual(set(REQUEST), keys)
        self.assertEqual(set(REPLY), keys)


class Helpers(unittest.TestCase):
    def test_a_missing_required_field_or_wrong_type_fails(self):
        with self.assertRaises(ValidationError):
            request_body("xfer", {"XferInfo": {"CurAmt": {"Amt": "not a number"}}})
        with self.assertRaises(ValidationError):
            reply("xfer", {"XferStatusRec": {"XferStatus": {"XferStatusCode": 7}}})

    def test_missing_and_null_are_different(self):
        # RecCtrlIn is optional and not nullable: left out it is absent, as null it is refused.
        body = {"AcctTrnSel": {"AcctKeys": {"AcctId": "5550010001", "AcctType": "DDA"}, "TrnPostType": "ExcludeMemoPost"}}
        self.assertEqual(request_body("trn", body), body)
        with self.assertRaises(ValidationError):
            request_body("trn", {**body, "RecCtrlIn": None})

    def test_a_history_row_without_an_optional_field_is_read_safely(self):
        recorded = next(body for key, side, status, body in EXCHANGES if key == "trn" and side == "response")
        changed = copy.deepcopy(recorded)
        changed["AcctTrnRec"][0]["AcctTrnInfo"].pop("PostedDt")
        from premier_demo.vendor_api import present
        self.assertIsNone(present(reply("trn", changed).acct_trn_rec[0].acct_trn_info.posted_dt))


class AmountPrecision(unittest.TestCase):
    """Money is Decimal end to end: exact on every read path and on the wire."""

    def client_with(self, reply_text):
        from premier_demo.client import PremierClient

        class Replay(PremierClient):
            def _post(self, key, body, *, write=False):
                # As the real _send does: the raw reply text parsed without floats.
                return json.loads(reply_text, parse_float=Decimal)
        return Replay.__new__(Replay)

    def recorded_reply(self, key):
        return copy.deepcopy(next(b for k, side, status, b in EXCHANGES if k == key and side == "response"))

    def text_with(self, key, select, raw_number):
        answer = self.recorded_reply(key)
        for entry in select(answer):
            entry["CurAmt"]["Amt"] = "@AMOUNT@"
        # The amount goes into the reply text exactly as written, as a bank would send it.
        return json.dumps(answer).replace('"@AMOUNT@"', raw_number), answer["AcctRec"]["AcctKeys"]["AcctId"]

    def test_every_read_path_shows_each_amount_exactly(self):
        balance = lambda a: [e for e in a["AcctRec"]["DepositAcctInfo"]["AcctBal"] if e["BalType"] == "Avail"]
        total = lambda a: [p for p in a["AcctRec"]["LoanAcctInfo"]["NextPmt"]["PmtCompositeAmt"]
                           if p["CompositeCurAmtType"] == "Total"]
        payoff = lambda a: [e for e in a["AcctRec"]["LoanAcctInfo"]["AcctBal"] if e["BalType"] == "PayOffAmt"]
        for raw, shown in (("9007199254740993", "9007199254740993.00"), ("0.1", "0.10"), ("0.2", "0.20"),
                           ("1250.07", "1250.07")):
            with self.subTest(amount=raw):
                text, account = self.text_with("dda", balance, raw)
                self.assertEqual(str(self.client_with(text).available_balance(account)), shown)
                text, account = self.text_with("loan", total, raw)
                self.assertEqual(self.client_with(text).loan_payment(account)["amount"], shown)
                text, account = self.text_with("loan", payoff, raw)
                self.assertEqual(self.client_with(text).current_payoff(account)["amount"], shown)

    def test_requests_carry_exact_numbers_on_the_wire(self):
        body = request_body("xfer", {"XferInfo": {
            "TransferType": "FundsTransfer",
            "FromAcctRef": {"AcctKeys": {"AcctId": "1", "AcctType": "DDA"}},
            "ToAcctRef": {"AcctKeys": {"AcctId": "2", "AcctType": "DDA"}},
            "CurAmt": {"Amt": Decimal("0.30"), "CurCode": {"CurCodeType": "ISO4217-Alpha", "CurCodeValue": "USD"}}}})
        self.assertIsInstance(body["XferInfo"]["CurAmt"]["Amt"], Decimal)
        self.assertIn('"Amt":0.30', dumps(body))
        self.assertEqual(dumps({"Amt": Decimal("9007199254740993")}), '{"Amt":9007199254740993}')


@unittest.skipUnless(importlib.util.find_spec("datamodel_code_generator"),
                     "the models group is not installed (uv sync --group models)")
class Regeneration(unittest.TestCase):
    def test_the_committed_models_match_a_fresh_generation_from_the_pinned_archive(self):
        from premier_demo.contract import MissingContractInput, load_members
        try:
            load_members()
        except MissingContractInput as error:
            self.skipTest(str(error))
        import make_models
        self.assertEqual(make_models.main(["--check"]), 0)


if __name__ == "__main__":
    unittest.main()
