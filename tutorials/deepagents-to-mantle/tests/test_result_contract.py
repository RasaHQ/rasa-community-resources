"""Result-boundary regressions, with no model, SDK or public data download."""
from contextlib import closing
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from shared import database


class ResultContract(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / "sample.sqlite"
        with closing(sqlite3.connect(self.path)) as connection:
            connection.execute("CREATE TABLE Invoice(value INTEGER)")
            connection.commit()
        self.before = self.path.read_bytes()
        environment = patch.dict(os.environ, {"CHINOOK_DATABASE": str(self.path)})
        environment.start()
        self.addCleanup(environment.stop)

    def tearDown(self):
        self.assertEqual(self.path.read_bytes(), self.before)

    def test_one_large_cell_is_refused_despite_limit_one(self):
        result = database.query("SELECT hex(zeroblob(65536)) AS value LIMIT 1")
        self.assertEqual(result["reason"], "sqlite_value_too_large")
        self.assertNotIn("rows", result)

    def test_plain_result_columns_can_together_exceed_the_sqlite_value_limit(self):
        result = database.query(
            "SELECT hex(zeroblob(8000)) AS a, hex(zeroblob(8000)) AS b, "
            "hex(zeroblob(8000)) AS c"
        )
        self.assertEqual(result["status"], "ok")
        self.assertEqual([len(value) for value in result["rows"][0]], [16000] * 3)
        self.assertGreater(sum(map(len, result["rows"][0])), database.MAX_SQLITE_VALUE_BYTES)
        encoded = json.dumps(result, ensure_ascii=True, allow_nan=False, separators=(",", ":"))
        self.assertLessEqual(len(encoded.encode("utf-8")), database.MAX_RESULT_JSON_BYTES)

    def test_sort_records_can_exceed_the_sqlite_length_limit(self):
        result = database.query(
            "SELECT hex(zeroblob(8000)) AS a, hex(zeroblob(8000)) AS b, "
            "hex(zeroblob(8000)) AS c FROM (SELECT 1 UNION ALL SELECT 2) "
            "ORDER BY a LIMIT 1"
        )
        self.assertEqual((result["status"], result["reason"]), ("error", "sqlite_value_too_large"))
        self.assertNotIn("rows", result)

    def test_small_binary_value_is_not_silently_stringified(self):
        result = database.query("SELECT zeroblob(8) AS value LIMIT 1")
        self.assertEqual(result["reason"], "unsupported_result_value")
        self.assertNotIn("rows", result)
        json.dumps(result, allow_nan=False)

    def test_nonfinite_number_is_not_a_json_infinity_extension(self):
        result = database.query("SELECT 1e999 AS value")
        self.assertEqual(result["reason"], "unsupported_result_value")
        json.dumps(result, allow_nan=False)

    def test_individually_small_rows_can_exceed_the_total_budget(self):
        sql = ("WITH RECURSIVE n(x) AS (SELECT 1 UNION ALL SELECT x+1 FROM n WHERE x<6) "
               "SELECT hex(zeroblob(6000)) FROM n")
        self.assertEqual(database.query(sql)["reason"], "result_too_large")

    def test_json_escaping_counts_even_when_raw_text_is_small(self):
        # Eight 1500-byte cells fit the value and row limits. JSON represents
        # each control character with six ASCII bytes, exceeding 64 KiB total.
        sql = ("WITH RECURSIVE n(x) AS (SELECT 1 UNION ALL SELECT x+1 FROM n WHERE x<8) "
               "SELECT replace(hex(zeroblob(1500)), '00', char(1)) FROM n")
        self.assertEqual(database.query(sql)["reason"], "result_too_large")

    def test_small_unicode_and_null_values_keep_their_types(self):
        result = database.query("SELECT 'café', NULL, 3.5")
        self.assertEqual(result["rows"], [["café", None, 3.5]])
        encoded = json.dumps(result, ensure_ascii=True, allow_nan=False, separators=(",", ":"))
        self.assertLessEqual(len(encoded.encode("utf-8")), database.MAX_RESULT_JSON_BYTES)

    def test_exact_success_budget_is_inclusive(self):
        expected = {"status": "ok", "columns": ["value"], "rows": [[1]]}
        size = len(json.dumps(expected, ensure_ascii=True, allow_nan=False,
                              separators=(",", ":")).encode("utf-8"))
        with patch.object(database, "MAX_RESULT_JSON_BYTES", size):
            self.assertEqual(database.checked_result(expected), expected)
        with patch.object(database, "MAX_RESULT_JSON_BYTES", size - 1):
            self.assertEqual(database.checked_result(expected)["reason"], "result_too_large")

    def test_schema_result_has_an_aggregate_budget(self):
        self.assertEqual(database.schema("Invoice")["status"], "ok")
        self.assertEqual(database.schema(",".join(["Invoice"] * 1500))["reason"], "result_too_large")

    def test_query_checker_cannot_echo_an_unbounded_statement(self):
        result = database.check_query("SELECT 1 /*" + "x" * 70000 + "*/")
        self.assertEqual(result["reason"], "result_too_large")
        self.assertNotIn("query", result)

    def test_failed_connection_setup_closes_before_returning_an_error(self):
        with patch.object(database.sqlite3, "connect") as factory:
            factory.return_value.setlimit.side_effect = sqlite3.OperationalError("limit setup failed")
            result = database.query("SELECT 1")
            self.assertEqual((result["status"], result["reason"]), ("error", "limit setup failed"))
            factory.return_value.close.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
