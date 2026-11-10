"""Exercise the replacement workbook through the unchanged importer and queries."""
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from scripts.generate_demo_sales import write_workbook
from lib.importer import import_all
from lib.database import get_executive_revenue_summary, search_menu

PROJECT = Path(__file__).resolve().parents[1]


class SyntheticSalesTests(unittest.TestCase):
    def test_regeneration_matches_committed_workbook(self):
        with tempfile.TemporaryDirectory() as directory:
            generated = Path(directory) / "sales.xlsx"
            write_workbook(generated)
            self.assertEqual(generated.read_bytes(),
                             (PROJECT / "data" / "Coffee Shop Sales.xlsx").read_bytes())

    def test_import_menu_and_revenue_with_isolated_database(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data = root / "data"
            data.mkdir()
            write_workbook(data / "Coffee Shop Sales.xlsx")
            for filename in ("customer_profiles.json", "raw_materials_costs.csv",
                             "product_recipes.csv", "store_inventory.json"):
                shutil.copyfile(PROJECT / "data" / filename, data / filename)
            with patch.dict(os.environ, {"PROJECT_ROOT": str(root)}):
                import_all(force=True)
                summary = get_executive_revenue_summary()
                self.assertEqual(summary["total_transactions"], 18)
                self.assertEqual(summary["total_revenue"], 81)
                self.assertEqual(summary["period_start"], "2026-09-01")
                self.assertEqual(summary["period_end"], "2026-09-02")
                self.assertEqual(get_executive_revenue_summary(store_id=5)["total_revenue"], 27)
                self.assertEqual(len(search_menu()), 3)
                self.assertEqual(search_menu(query="Ethiopian")[0]["unit_price"], 3)


if __name__ == "__main__":
    unittest.main()
