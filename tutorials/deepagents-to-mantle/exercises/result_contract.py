"""Inspect a trusted local SQL helper, without loading either agent runtime.

--source executes that Python file. Use only your own reviewed checkout or the
explicit historical source export described in RESULTS.md.
"""
import argparse
from contextlib import closing
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import sqlite3
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
CASES = (
    ("ordinary scalar", "SELECT 1 AS value"),
    ("one large text cell", "SELECT hex(zeroblob(65536)) AS value LIMIT 1"),
    ("eight-byte binary cell", "SELECT zeroblob(8) AS value LIMIT 1"),
    ("nonfinite number", "SELECT 1e999 AS value"),
    ("six small text rows", "WITH RECURSIVE n(x) AS (SELECT 1 UNION ALL SELECT x+1 FROM n WHERE x<6) SELECT hex(zeroblob(6000)) FROM n"),
    ("eight escaped text rows", "WITH RECURSIVE n(x) AS (SELECT 1 UNION ALL SELECT x+1 FROM n WHERE x<8) SELECT replace(hex(zeroblob(1500)), '00', char(1)) FROM n"),
)


def inspect_source(source: Path) -> dict:
    source = source.resolve(strict=True)
    specification = importlib.util.spec_from_file_location("result_contract_subject", source)
    helper = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(helper)
    reports = []
    with tempfile.TemporaryDirectory(prefix="sql-result-exercise-") as temporary:
        path = Path(temporary) / "sample.sqlite"
        with closing(sqlite3.connect(path)) as connection:
            connection.execute("CREATE TABLE Example(value INTEGER)")
            connection.commit()
        before = hashlib.sha256(path.read_bytes()).hexdigest()
        with patch.dict(os.environ, {"CHINOOK_DATABASE": str(path)}):
            for label, sql in CASES:
                result = helper.query(sql)
                report = {"case": label, "status": result["status"],
                          "reason": result.get("reason"), "rows": len(result.get("rows", []))}
                try:
                    encoded = json.dumps(result, ensure_ascii=True, allow_nan=False,
                                         separators=(",", ":"))
                    report.update(json="ok", jsonUtf8Bytes=len(encoded.encode("utf-8")))
                except (TypeError, ValueError) as error:
                    report.update(json=type(error).__name__, jsonUtf8Bytes=None)
                reports.append(report)
        unchanged = before == hashlib.sha256(path.read_bytes()).hexdigest()
        if not unchanged:
            raise RuntimeError("The exercise changed its database")
    return {"scope": "Shared helper and strict canonical JSON only; no SDK, wrapper or model execution",
            "sourceSha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            "python": platform.python_version(), "sqlite": sqlite3.sqlite_version,
            "databaseUnchanged": unchanged, "cases": reports}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT / "shared/database.py")
    args = parser.parse_args()
    print(json.dumps(inspect_source(args.source), indent=2, allow_nan=False))
