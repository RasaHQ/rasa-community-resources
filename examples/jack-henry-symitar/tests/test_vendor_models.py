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

    def test_no_recorded_field_is_left_undeclared_by_its_model(self):
        # extra="allow" would otherwise hide a field the generator dropped.
        from pydantic import BaseModel, RootModel

        def undeclared(value, where):
            if isinstance(value, RootModel):
                return undeclared(value.root, where)
            if isinstance(value, BaseModel):
                found = [f"{where}.{key}" for key in (value.model_extra or {})]
                for name in type(value).model_fields:
                    found += undeclared(getattr(value, name), f"{where}.{name}")
                return found
            if isinstance(value, list):
                return [item for index, entry in enumerate(value) for item in undeclared(entry, f"{where}[{index}]")]
            return []

        for operation, side, status, media, body in EXCHANGES:
            if body is None:
                continue
            model = REQUEST[operation] if side == "request" else REPLY[operation] if status == 200 else PROBLEM[operation]
            with self.subTest(operation=operation, side=side, status=status):
                self.assertEqual(undeclared(model.model_validate(body), operation), [])

    def test_a_field_named_description_is_part_of_the_model(self):
        from vendor_models.transactions import Transaction
        self.assertIn("description", Transaction.model_fields)

    def test_a_reply_without_an_optional_field_is_read_safely(self):
        from vendor_models.transactions import Transaction
        recorded = next(body for operation, side, status, media, body in EXCHANGES
                        if operation == "searchAccountTransactions" and side == "response")
        row = dict(recorded["transactions"][0])
        row.pop("description")
        from vendor_api import present
        self.assertIsNone(present(Transaction.model_validate(row).description))

    def test_missing_and_null_are_different(self):
        # loanId is optional and not nullable: it may be left out, but never sent as null.
        self.assertEqual(request_body("searchLoans", accountNumber="0000000001"), {"accountNumber": "0000000001"})
        with self.assertRaises(ValidationError):
            request_body("searchLoans", accountNumber="0000000001", loanId=None)
        # receiptId is nullable: null is accepted and kept.
        receipt = {"status": "success", "receiptId": None, "confirmationNumber": None}
        self.assertEqual(REPLY["postTransfer"].model_validate(receipt).model_dump(mode="json", by_alias=True,
                                                                                  exclude_unset=True), receipt)
        # status is optional and not nullable: leaving it out is fine, null is refused.
        self.assertEqual(REPLY["postTransfer"].model_validate({}).model_dump(mode="json", exclude_unset=True), {})
        with self.assertRaises(ValidationError):
            reply("postTransfer", {"status": None})

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
