# SPDX-License-Identifier: MIT
"""The generated Symitar models match the example's own recorded traffic. Vendor-free."""
import importlib.util
import unittest

from pydantic import ValidationError

from recorded_exchanges import EXCHANGES
from vendor_api import PROBLEM, REPLY, REQUEST, reply, request_body


class RecordedTrafficRoundTrip(unittest.TestCase):
    def test_every_recorded_exchange_parses_into_its_model_and_comes_back_unchanged(self):
        checked = 0
        for operation, side, status, media, body in EXCHANGES:
            with self.subTest(operation=operation, side=side, status=status):
                if body is None:  # a declared bodiless reply (401): nothing to model
                    self.assertEqual((side, media), ("response", ""))
                    continue
                if side == "request":
                    model = REQUEST[operation]
                elif status == 200:
                    model = REPLY[operation]
                else:
                    model = PROBLEM[operation]
                again = model.model_validate(body).model_dump(mode="json", by_alias=True, exclude_unset=True)
                self.assertEqual(again, body)
                checked += 1
        self.assertEqual(checked, 13)

    def test_every_operation_has_a_request_and_a_reply_model(self):
        operations = {operation for operation, *_ in EXCHANGES}
        self.assertEqual(set(REQUEST), operations)
        self.assertEqual(set(REPLY), operations)


class Helpers(unittest.TestCase):
    def test_request_bodies_are_built_through_the_model(self):
        self.assertEqual(request_body("searchLoans", accountNumber="0000000001", loanId="0001"),
                         {"accountNumber": "0000000001", "loanId": "0001"})
        body = request_body("postTransfer", donor={"accountNumber": "1", "shareId": "0001"},
                            recipient={"accountNumber": "1", "shareId": "0002"}, amount="25.00")
        self.assertEqual(body["amount"], "25.00")

    def test_a_missing_required_field_or_wrong_type_fails(self):
        with self.assertRaises(ValidationError):
            request_body("postTransfer", donor={"accountNumber": "1", "shareId": "0001"}, amount="25.00")
        with self.assertRaises(ValidationError):
            request_body("searchLoans", accountNumber=["not", "a", "string"])

    def test_replies_are_read_as_typed_models(self):
        transfer = reply("postTransfer", {"status": "success", "confirmationNumber": None, "receiptId": None})
        self.assertEqual(transfer.status, "success")
        with self.assertRaises(ValidationError):
            reply("postTransfer", {"status": "invented"})


@unittest.skipUnless(importlib.util.find_spec("datamodel_code_generator"),
                     "the models group is not installed (uv sync --group models)")
class Regeneration(unittest.TestCase):
    def test_the_committed_models_match_a_fresh_generation_from_the_pinned_files(self):
        from contract_inputs import MissingContractInput, load_inputs
        try:
            load_inputs()
        except MissingContractInput as error:
            self.skipTest(str(error))
        import make_models
        self.assertEqual(make_models.main(["--check"]), 0)


if __name__ == "__main__":
    unittest.main()
