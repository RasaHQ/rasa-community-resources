"""Historical operation replay versus current allocation in an invented seat ledger."""
from __future__ import annotations

import json
import sqlite3
import tempfile
from pathlib import Path


def connect(path):
    db = sqlite3.connect(path, timeout=5)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    db.executescript('''
      CREATE TABLE IF NOT EXISTS flights (
        flight TEXT PRIMARY KEY, capacity INTEGER NOT NULL,
        remaining INTEGER NOT NULL CHECK(remaining>=0 AND remaining<=capacity));
      CREATE TABLE IF NOT EXISTS reservations (
        reservation TEXT PRIMARY KEY, flight TEXT NOT NULL REFERENCES flights,
        passenger TEXT NOT NULL, state TEXT NOT NULL CHECK(state IN ('active','cancelled')),
        version INTEGER NOT NULL);
      CREATE TABLE IF NOT EXISTS operations (
        request TEXT PRIMARY KEY, reservation TEXT NOT NULL REFERENCES reservations,
        flight TEXT NOT NULL, passenger TEXT NOT NULL,
        outcome TEXT NOT NULL CHECK(outcome='reserved'));
    ''')
    return db


def initialize(path):
    db = connect(path)
    try:
        with db:
            db.execute('INSERT INTO flights VALUES (?,?,?)', ('F1', 1, 1))
    finally:
        db.close()


def reserve(path, request, passenger, flight='F1', *, audit=None):
    if not all(isinstance(value, str) and value for value in (request, passenger, flight)):
        raise ValueError('Explicit operation, passenger and flight identities required')
    db = connect(path)
    try:
        db.execute('BEGIN IMMEDIATE')
        prior = db.execute('SELECT * FROM operations WHERE request=?', (request,)).fetchone()
        if prior:
            if (prior['passenger'], prior['flight']) != (passenger, flight):
                raise ValueError('Operation identity belongs to different facts')
            db.commit()
            if audit is not None:
                audit.append({'kind': 'operation_replay', 'changed_rows': db.total_changes})
            return dict(prior)  # Correct replay of the original operation, not a status query.
        changed = db.execute('UPDATE flights SET remaining=remaining-1 WHERE flight=? AND remaining>0', (flight,)).rowcount
        if not changed:
            db.rollback()
            return {'request': request, 'outcome': 'unavailable'}
        reservation = 'reservation:' + request  # Synthetic IDs; not an authentication scheme.
        db.execute('INSERT INTO reservations VALUES (?,?,?,?,?)',
                   (reservation, flight, passenger, 'active', 1))
        db.execute('INSERT INTO operations VALUES (?,?,?,?,?)',
                   (request, reservation, flight, passenger, 'reserved'))
        db.commit()
        return {'request': request, 'reservation': reservation,
                'flight': flight, 'passenger': passenger, 'outcome': 'reserved'}
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def cancel(path, reservation):
    db = connect(path)
    try:
        db.execute('BEGIN IMMEDIATE')
        row = db.execute('SELECT * FROM reservations WHERE reservation=?', (reservation,)).fetchone()
        if row is None:
            raise ValueError('Unknown reservation')
        changed = db.execute("UPDATE reservations SET state='cancelled',version=version+1 WHERE reservation=? AND state='active'",
                             (reservation,)).rowcount
        if changed:
            db.execute('UPDATE flights SET remaining=remaining+1 WHERE flight=?', (row['flight'],))
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def read_current(path, reservation):
    db = connect(path)
    try:
        row = db.execute('SELECT * FROM reservations WHERE reservation=?', (reservation,)).fetchone()
        return dict(row) if row else None
    finally:
        db.close()


def answer_allocation(receipt, current):
    """Answer whether the reservation is allocated at the supplied observation."""
    result = {'operation_outcome': receipt['outcome'], 'is_allocated': None}
    if current is None:
        return result
    if receipt['outcome'] != 'reserved' or any(
        current[key] != receipt[key] for key in ('reservation', 'flight', 'passenger')
    ):
        raise ValueError('Observation belongs to another reservation')
    return {**result, 'is_allocated': current['state'] == 'active',
            'reservation_state': current['state'], 'observed_version': current['version']}


def inventory(path):
    db = connect(path)
    try:
        return {'remaining': db.execute('SELECT remaining FROM flights WHERE flight=?', ('F1',)).fetchone()[0],
                'reservations': [dict(row) for row in db.execute('SELECT * FROM reservations ORDER BY reservation')],
                'active': [dict(row) for row in db.execute("SELECT * FROM reservations WHERE state='active' ORDER BY reservation")],
                'operations': [dict(row) for row in db.execute('SELECT * FROM operations ORDER BY request')]}
    finally:
        db.close()


def demo():
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / 'seats.db'
        initialize(path)
        original = reserve(path, 'request-A', 'passenger-A')
        cancel(path, original['reservation'])
        replacement = reserve(path, 'request-B', 'passenger-B')
        before_retry = inventory(path)
        audit = []
        replay = reserve(path, 'request-A', 'passenger-A', audit=audit)
        current = read_current(path, original['reservation'])
        return {'kind': 'synthetic_local_operation_and_resource_contract',
                'original_receipt': original, 'new_passenger_receipt': replacement,
                'replayed_receipt': replay, 'identical_receipt': original == replay,
                'receipt_only_is_allocated': replay['outcome'] == 'reserved',
                'observed_allocation_answer': answer_allocation(replay, current),
                'inventory_before_retry': before_retry, 'inventory_after_retry': inventory(path),
                'replay_sql_rows_changed': audit[0]['changed_rows'],
                'ledger_after_retry_unchanged': before_retry == inventory(path)}


if __name__ == '__main__':
    print(json.dumps(demo(), indent=2, sort_keys=True))
