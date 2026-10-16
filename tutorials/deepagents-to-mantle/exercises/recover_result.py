"""Try smaller SQL results using a temporary database and the shared helper.

No SDK, public data download, model or provider access is used. The queries
are fixed teaching inputs, not automatic repairs of arbitrary SQL.
"""
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

SOURCE = Path(__file__).resolve().parents[1] / 'shared/database.py'
CASES = (
    ('trim-after-generation',
     'SELECT substr(hex(zeroblob(65536)), 1, 80) AS preview'),
    ('generate-smaller-value',
     'SELECT hex(zeroblob(40)) AS preview'),
    ('summarise-six-values',
     'WITH RECURSIVE n(x) AS (SELECT 1 UNION ALL SELECT x+1 FROM n WHERE x<6) '
     'SELECT count(*) AS row_count, sum(length(hex(zeroblob(6000)))) AS character_count FROM n'),
    ('summarise-escaped-values',
     'WITH RECURSIVE n(x) AS (SELECT 1 UNION ALL SELECT x+1 FROM n WHERE x<8) '
     "SELECT count(*) AS row_count, sum(length(replace(hex(zeroblob(1500)), '00', char(1)))) AS character_count FROM n"),
)


def run():
    spec = importlib.util.spec_from_file_location('recovery_subject', SOURCE)
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    reports = []
    with tempfile.TemporaryDirectory(prefix='sql-recovery-exercise-') as temporary:
        database = Path(temporary) / 'sample.sqlite'
        with closing(sqlite3.connect(database)) as connection:
            connection.execute('CREATE TABLE Example(value INTEGER)')
            connection.commit()
        before = hashlib.sha256(database.read_bytes()).hexdigest()
        with patch.dict(os.environ, {'CHINOOK_DATABASE': str(database)}):
            for name, sql in CASES:
                result = helper.query(sql)
                encoded = json.dumps(result, ensure_ascii=True, allow_nan=False,
                                     separators=(',', ':')).encode('utf-8')
                reports.append({'case': name, 'sql': sql, 'result': result,
                                'jsonUtf8Bytes': len(encoded)})
        unchanged = before == hashlib.sha256(database.read_bytes()).hexdigest()
        if not unchanged:
            raise RuntimeError('The exercise changed its database')
    return {'scope': 'Fixed-query helper exercise; no model or automatic query repair',
            'sourceSha256': hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
            'python': platform.python_version(), 'sqlite': sqlite3.sqlite_version,
            'databaseUnchanged': unchanged, 'cases': reports}


if __name__ == '__main__':
    print(json.dumps(run(), indent=2, allow_nan=False))
