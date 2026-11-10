from contextlib import closing
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from shared import database


class ReadOnlyTools(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "store.sqlite"
        with closing(sqlite3.connect(self.path)) as connection:
            connection.executescript("CREATE TABLE Invoice(InvoiceId INTEGER PRIMARY KEY, BillingCountry TEXT, Total NUMERIC); INSERT INTO Invoice VALUES(1,'Canada',3.5),(2,'Canada',4.0),(3,'UK',2.0);")
            connection.commit()
        self.before = self.path.read_bytes()
        self.env = patch.dict(os.environ, {"CHINOOK_DATABASE": str(self.path)})
        self.env.start()
        self.addCleanup(self.env.stop)

    def tearDown(self):
        self.assertEqual(self.path.read_bytes(), self.before)

    def test_sum_is_revenue_not_invoice_count(self):
        self.assertEqual(database.query("SELECT SUM(Total) FROM Invoice WHERE BillingCountry='Canada'")["rows"], [[7.5]])

    def test_schema_and_table_names(self):
        self.assertEqual(database.list_tables()["rows"], [["Invoice"]])
        self.assertIn("BillingCountry", database.schema("Invoice")["tables"][0]["create_sql"])

    def test_schema_does_not_accept_injected_identifier(self):
        self.assertEqual(database.schema("Invoice; DROP TABLE Invoice")["status"], "error")

    def test_write_attachment_and_sensitive_operations_refused(self):
        for sql in ["DELETE FROM Invoice", "UPDATE Invoice SET Total=0", "DROP TABLE Invoice", "CREATE TABLE X(a)", "ATTACH DATABASE ':memory:' AS extra", "PRAGMA writable_schema=ON", "SELECT load_extension('untrusted')"]:
            with self.subTest(sql=sql):
                self.assertEqual(database.query(sql)["status"], "error")

    def test_multi_statement_refused(self):
        self.assertEqual(database.query("SELECT 1; DELETE FROM Invoice")["status"], "error")

    def test_bad_sql_can_be_corrected(self):
        self.assertEqual(database.query("SELECT Unknown FROM Invoice")["status"], "error")
        self.assertEqual(database.query("SELECT Total FROM Invoice ORDER BY InvoiceId LIMIT 1")["rows"], [[3.5]])

    def test_compilation_does_not_execute_or_change_records(self):
        self.assertEqual(database.check_query("SELECT SUM(Total) FROM Invoice")["status"], "ok")
        self.assertEqual(database.check_query("DELETE FROM Invoice")["status"], "error")

    def test_row_bound_refuses_instead_of_truncating(self):
        self.assertEqual(database.query("WITH RECURSIVE x(n) AS (SELECT 1 UNION ALL SELECT n+1 FROM x WHERE n<101) SELECT n FROM x")["reason"], "too_many_rows")

    def test_work_bound_interrupts_recursive_query(self):
        self.assertEqual(database.query("WITH RECURSIVE x(n) AS (SELECT 1 UNION ALL SELECT n+1 FROM x) SELECT SUM(n) FROM x")["status"], "error")

if __name__ == "__main__":
    unittest.main()
