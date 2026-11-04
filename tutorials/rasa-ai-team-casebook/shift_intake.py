"""Synthetic absence intake: compare rollback boundaries, not HR policy."""
from __future__ import annotations

import json
import sqlite3
import tempfile
from pathlib import Path


def connect(path):
    db = sqlite3.connect(path)
    db.executescript('''
        CREATE TABLE IF NOT EXISTS absence (
          request_id TEXT PRIMARY KEY, employee TEXT NOT NULL, shift TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS swaps (
          request_id TEXT PRIMARY KEY REFERENCES absence(request_id),
          replacement TEXT NOT NULL);
    ''')
    db.execute('PRAGMA foreign_keys = ON')
    return db


def _report(db, request, employee, shift):
    if not all(isinstance(x, str) and x.strip() for x in (request, employee, shift)):
        raise ValueError('Nonempty request, employee and shift required')
    previous = db.execute('SELECT employee, shift FROM absence WHERE request_id=?',
                          (request,)).fetchone()
    if previous and previous != (employee, shift):
        raise ValueError('Request identity already names another absence')
    db.execute('INSERT OR IGNORE INTO absence VALUES (?, ?, ?)',
               (request, employee, shift))


def _swap(db, request, replacement, qualified):
    # Deliberately tiny fixture policy; no real staffing authority.
    if qualified is not True or not isinstance(replacement, str) or not replacement.strip():
        raise ValueError('No qualified replacement')
    old = db.execute('SELECT replacement FROM swaps WHERE request_id=?', (request,)).fetchone()
    if old and old != (replacement,):
        raise ValueError('Swap request already resolved with another replacement')
    db.execute('INSERT OR IGNORE INTO swaps VALUES (?, ?)', (request, replacement))


def submit(path, request, employee, shift, replacement, qualified, *, separate=True):
    db = connect(path)
    try:
        if separate:
            with db:
                _report(db, request, employee, shift)
            # A failed optional operation cannot roll back the committed report.
            try:
                with db:
                    _swap(db, request, replacement, qualified)
            except ValueError as error:
                return {'absence': 'recorded', 'swap': 'denied', 'reason': str(error)}
            return {'absence': 'recorded', 'swap': 'approved_in_fixture'}
        try:
            with db:
                _report(db, request, employee, shift)
                _swap(db, request, replacement, qualified)
        except ValueError as error:
            return {'request': 'denied', 'reason': str(error)}
        return {'request': 'approved_in_fixture'}
    finally:
        db.close()


def persisted(path):
    db = connect(path)
    try:
        return {table: db.execute('SELECT * FROM ' + table + ' ORDER BY request_id').fetchall()
                for table in ('absence', 'swaps')}
    finally:
        db.close()


def demo():
    result = {}
    with tempfile.TemporaryDirectory() as folder:
        for separate in (False, True):
            path = Path(folder) / ('separate.db' if separate else 'atomic.db')
            response = submit(path, 'a1', 'employee-1', 'night-1', 'employee-2', False,
                              separate=separate)
            result['separate' if separate else 'single_transaction'] = {
                'response': response, 'after_reopen': persisted(path)}
    return result


if __name__ == '__main__':
    print(json.dumps(demo(), indent=2, sort_keys=True))
