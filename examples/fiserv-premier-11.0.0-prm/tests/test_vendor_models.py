# SPDX-License-Identifier: MIT
"""The generated Premier models match the example's own recorded traffic. Vendor-free."""
import copy
import importlib.util
import unittest

from pydantic import ValidationError

from premier_demo.recorded_exchanges import EXCHANGES
from premier_demo.vendor_api import REPLY, REQUEST, reply, request_body


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
                again = model.model_validate(body).model_dump(mode="json", by_alias=True, exclude_unset=True)
                self.assertEqual(again, body)
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

    def test_a_history_row_without_an_optional_field_is_read_safely(self):
        recorded = next(body for key, side, status, body in EXCHANGES if key == "trn" and side == "response")
        changed = copy.deepcopy(recorded)
        changed["AcctTrnRec"][0]["AcctTrnInfo"].pop("PostedDt")
        self.assertIsNone(reply("trn", changed).acct_trn_rec[0].acct_trn_info.posted_dt)


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
