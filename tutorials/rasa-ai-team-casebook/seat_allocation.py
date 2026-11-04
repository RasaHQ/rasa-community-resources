"""Synthetic seat allocation; no airline, fare, or ticketing integration."""
from __future__ import annotations
import json
import sqlite3
import tempfile
from pathlib import Path


def connect(path):
    db = sqlite3.connect(path, timeout=5)
    db.execute('PRAGMA foreign_keys=ON')
    db.executescript('''
      CREATE TABLE IF NOT EXISTS flights (flight TEXT PRIMARY KEY, remaining INTEGER NOT NULL CHECK(remaining>=0));
      CREATE TABLE IF NOT EXISTS reservations (request_id TEXT PRIMARY KEY, flight TEXT NOT NULL REFERENCES flights(flight));
    ''')
    return db


def initialize(path):
    db = connect(path)
    try:
        with db:
            db.execute('INSERT INTO flights VALUES (?, ?)', ('F1', 1))
            db.execute('INSERT INTO flights VALUES (?, ?)', ('F2', 1))
    finally: db.close()


def reserve(path, request_id, flight):
    if not all(isinstance(v, str) and v.strip() for v in (request_id, flight)):
        raise ValueError('Nonempty reservation identity and flight required')
    db = connect(path)
    try:
        # Serialize both identity lookup and seat spending, not just the decrement.
        db.execute('BEGIN IMMEDIATE')
        prior = db.execute('SELECT flight FROM reservations WHERE request_id=?', (request_id,)).fetchone()
        if prior:
            if prior != (flight,): raise ValueError('Reservation identity names another flight')
            db.commit()
            return 'reserved_replay'
        changed = db.execute('UPDATE flights SET remaining=remaining-1 WHERE flight=? AND remaining>0', (flight,)).rowcount
        if not changed:
            db.rollback()
            return 'unavailable'
        db.execute('INSERT INTO reservations VALUES (?, ?)', (request_id, flight))
        db.commit()
        return 'reserved'
    except Exception:
        db.rollback()
        raise
    finally: db.close()


def inventory(path):
    db = connect(path)
    try:
        return {'flights': db.execute('SELECT * FROM flights ORDER BY flight').fetchall(),
                'reservations': db.execute('SELECT * FROM reservations ORDER BY request_id').fetchall()}
    finally: db.close()


def stale_read_demo(path):
    """Controlled interleaving: both reads occur before either write."""
    readers = [connect(path), connect(path)]
    try:
        snapshots = [db.execute('SELECT remaining FROM flights WHERE flight=?', ('F1',)).fetchone()[0] for db in readers]
        for i, (db, remaining) in enumerate(zip(readers, snapshots)):
            if remaining:
                with db:
                    # The plausible absolute write avoids a negative counter but loses an allocation.
                    db.execute('UPDATE flights SET remaining=? WHERE flight=?', (remaining - 1, 'F1'))
                    db.execute('INSERT INTO reservations VALUES (?, ?)', ('request-' + str(i), 'F1'))
        return snapshots
    finally:
        for db in readers: db.close()


def demo():
    out = {}
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder)/'naive.db'; initialize(path)
        out['stale_reads'] = {'observed_available': stale_read_demo(path), 'stored': inventory(path)}
        path = Path(folder)/'conditional.db'; initialize(path)
        outcomes = [reserve(path, 'a', 'F1'), reserve(path, 'b', 'F1'), reserve(path, 'a', 'F1')]
        out['transaction'] = {'outcomes': outcomes, 'stored': inventory(path)}
    return out


if __name__ == '__main__': print(json.dumps(demo(), indent=2, sort_keys=True))
