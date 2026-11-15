"""Initial setup preserves existing cells and never repeats an uncertain append."""
from copy import deepcopy
from typing import Any
import unittest

from pydantic import BaseModel

from shop_demo.setup_sheet import prepare
from shop_demo.table_schema import PRODUCT_COLUMNS, ORDER_COLUMNS


class Result(BaseModel):
    success: bool = True
    content: dict[str, Any]


class SheetService:
    def __init__(self, rows=None, *, fail_append=False):
        self.rows = deepcopy(rows or {})
        self.creates, self.appends, self.fail_append = [], [], fail_append

    def get_spreadsheet(self, spreadsheet_id):
        return Result(content={"sheets": [{"properties": {"title": name}} for name in self.rows]})

    def batch_update(self, spreadsheet_id, requests):
        for request in requests:
            self.assert_only_add(request)
            name = request["addSheet"]["properties"]["title"]
            self.rows[name] = []
            self.creates.append(name)
        return Result(content={})

    def assert_only_add(self, request):
        if set(request) != {"addSheet"}:
            raise AssertionError("Only tab creation is allowed")

    def get_values(self, spreadsheet_id, range_a1):
        name = range_a1.strip("'")
        return Result(content={"values": deepcopy(self.rows[name])})

    def append_values(self, spreadsheet_id, range_a1, rows, *, value_input_option):
        if value_input_option != "RAW":
            raise AssertionError("Only RAW writes are allowed")
        self.appends.append((range_a1, deepcopy(rows)))
        if self.fail_append:
            return Result(success=False, content={})
        name = range_a1.split("!")[0].strip("'")
        # Google's formatted readback may contain integer cells as strings.
        self.rows[name].extend([[str(cell) if type(cell) is int else cell for cell in row] for row in rows])
        return Result(content={})


class SetupTests(unittest.TestCase):
    def test_blank_sheet_creates_two_tabs_and_seeds_once(self):
        service = SheetService()
        outcomes = prepare(service, "synthetic-sheet")
        self.assertEqual(service.creates, ["Products", "Orders"])
        self.assertEqual(service.rows["Products"][0], list(PRODUCT_COLUMNS))
        self.assertEqual(service.rows["Orders"], [list(ORDER_COLUMNS)])
        self.assertEqual(service.rows["Products"][1], ["NOTEBOOK", "Notebook", "12900", "12"])
        self.assertEqual([outcome.action for outcome in outcomes], ["seeded", "seeded"])
        prepare(service, "synthetic-sheet")
        self.assertEqual(len(service.appends), 2)

    def test_existing_partial_or_blank_result_rows_are_preserved(self):
        original = {"Products": [["existing text outside the schema"]], "Orders": [[""]]}
        service = SheetService(original)
        outcomes = prepare(service, "synthetic-sheet")
        self.assertEqual(service.rows, original)
        self.assertEqual(service.appends, [])
        self.assertEqual(service.creates, [])
        self.assertEqual([outcome.action for outcome in outcomes], ["preserved", "preserved"])

    def test_missing_orders_tab_is_created_without_touching_products(self):
        original = [["existing catalog"]]
        service = SheetService({"Products": original})
        prepare(service, "synthetic-sheet")
        self.assertEqual(service.rows["Products"], original)
        self.assertEqual(service.creates, ["Orders"])
        self.assertEqual(len(service.appends), 1)

    def test_uncertain_append_stops_without_a_second_write(self):
        service = SheetService(fail_append=True)
        with self.assertRaises(RuntimeError):
            prepare(service, "synthetic-sheet")
        self.assertEqual(len(service.appends), 1)


if __name__ == "__main__":
    unittest.main()
