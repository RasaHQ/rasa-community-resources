# SPDX-License-Identifier: MIT
"""The generated Banking Hub models match the example's own recorded traffic. Vendor-free."""
import copy
import importlib.util
import unittest

from pydantic import ValidationError

from bh_demo.recorded_exchanges import EXCHANGES
from bh_demo.vendor_api import REPLY, REQUEST, present, reply, request_body


class RecordedTrafficRoundTrip(unittest.TestCase):
    def test_every_recorded_body_parses_into_its_model_and_comes_back_unchanged(self):
        # The models ignore undeclared fields, so a field lost in generation would be missing here.
        for key, side, status, body in EXCHANGES:
            with self.subTest(key=key, side=side, status=status):
                model = REQUEST[key] if side == "request" else REPLY[key]
                again = model.model_validate(body).model_dump(mode="json", by_alias=True, exclude_unset=True)
                self.assertEqual(again, body)
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
