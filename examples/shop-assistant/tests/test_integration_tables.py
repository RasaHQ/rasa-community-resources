from types import SimpleNamespace
import unittest
from shop_demo.integration_tables import GoogleTables
from shop_demo.sheets import SheetFailure


class TableAdapterTests(unittest.TestCase):
    def test_fixed_ranges_and_raw_order_values(self):
        calls = []

        class Service:
            def get_values(self, sheet, range_):
                calls.append((sheet, range_))
                return SimpleNamespace(success=True, content={"values": [["Code"]]})

            def append_values(self, sheet, range_, values, **kwargs):
                calls.append((sheet, range_, values, kwargs))
                return SimpleNamespace(success=True)
        tables = GoogleTables(Service(), "synthetic_sheet")
        self.assertEqual(tables.read("Products"), [["Code"]])
        row = ["number", "=literal", 100, "MXN", "placed", "time", "request"]
        tables.append("Orders", row)
        self.assertEqual(calls[-1][3], {"value_input_option": "RAW"})
        self.assertEqual(calls[-1][2], [row])
        with self.assertRaises(SheetFailure):
            tables.append("Products", row)
        with self.assertRaises(SheetFailure):
            tables.read("Arbitrary!A1")

    def test_provider_failure_is_sanitized_without_retry(self):
        calls = []

        class Service:
            def append_values(self, *args, **kwargs):
                calls.append(1)
                raise RuntimeError("synthetic provider detail")
        with self.assertRaisesRegex(SheetFailure, "SHEET_APPEND_UNCERTAIN") as error:
            GoogleTables(Service(), "test").append("Orders", ["x"] * 7)
        self.assertNotIn("provider detail", str(error.exception))
        self.assertEqual(calls, [1])
