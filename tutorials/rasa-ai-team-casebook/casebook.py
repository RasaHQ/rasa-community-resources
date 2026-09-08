#!/usr/bin/env python3
"""Synthetic evidence and retry lab. No network or real customer actions.

Facts are trusted lab inputs, NEVER parameters a production model may assert.
SQLite is the synthetic backend and request ledger together, in one transaction.
This deliberately does not claim atomicity with a separate real service.
"""
from __future__ import annotations
import argparse
from contextlib import closing
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import tempfile

ROOT = Path(__file__).resolve().parent


def load_case(slug: str) -> dict:
    if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', slug):
        raise ValueError('Invalid case identifier')
    path = ROOT / 'examples' / f'{slug}.json'
    if not path.is_file():
        raise ValueError('Unknown case identifier')
    spec = json.loads(path.read_text())
    if spec['slug'] != slug or len(spec['rules']) != 3:
        raise ValueError('Invalid scenario contract')
    if any(r['phase'] not in ('request', 'receipt') for r in spec['rules']):
        raise ValueError('Unknown evidence phase')
    return spec


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def connect(path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute('''CREATE TABLE IF NOT EXISTS requests (
        request_id TEXT PRIMARY KEY, case_id TEXT NOT NULL,
        fingerprint TEXT NOT NULL, status TEXT NOT NULL,
        reason TEXT NOT NULL, reference TEXT NOT NULL,
        contract_hash TEXT NOT NULL)''')
    conn.execute('''CREATE TABLE IF NOT EXISTS intakes (
        request_id TEXT PRIMARY KEY, case_id TEXT NOT NULL,
        kind TEXT NOT NULL, reference TEXT NOT NULL)''')
    return conn


def record_intake(spec: dict, request_id: str, database: str | Path) -> dict:
    """Record an unverified observation/request without approving a later action.

    Explicit operator/confirmed-user choice, not a side effect of an offer.
    No qualification, clearance, incident-match or offer predicate gates this
    separate intake. These synthetic records contain no customer payload.
    """
    kind = spec.get('intakeKind')
    if kind not in ('arrival-observation', 'absence-report', 'cancellation-request', 'unmatched-outage-report'):
        raise ValueError('This case has no independent intake transition')
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,79}', request_id):
        raise ValueError('Invalid request identifier')
    with closing(connect(database)) as conn, conn:
        conn.execute('BEGIN IMMEDIATE')
        prior = conn.execute('SELECT * FROM intakes WHERE request_id = ?', (request_id,)).fetchone()
        if prior and (prior['case_id'] != spec['slug'] or prior['kind'] != kind):
            return result('conflict', 'intake_identity_changed')
        reference = 'INTAKE-' + digest({'case': spec['slug'], 'request': request_id, 'kind': kind})[:12]
        if not prior:
            conn.execute('INSERT INTO intakes VALUES (?, ?, ?, ?)', (request_id, spec['slug'], kind, reference))
    return dict(result('recorded', 'intake_is_not_action_approval', reference, 0, bool(prior)), intakeKind=kind, recordedIntakes=1)


def lookup_intake(database: str | Path, request_id: str) -> dict:
    with closing(connect(database)) as conn:
        row = conn.execute('SELECT * FROM intakes WHERE request_id = ?', (request_id,)).fetchone()
    if row is None:
        return result('unknown', 'no_local_intake')
    return dict(result('recorded', 'intake_is_not_action_approval', row['reference'], 0, True), intakeKind=row['kind'], recordedIntakes=1)


def evaluate(spec: dict, facts: dict, phase: str) -> str | None:
    for rule in spec['rules']:
        if rule['phase'] == phase and facts.get(rule['field']) is not True:
            return rule['reason']
    return None


def result(status, reason, reference=None, effects=0, replay=False):
    return dict(status=status, reason=reason, reference=reference,
                effects=effects, replay=replay, evidenceKind='synthetic')


def contract_hash(spec: dict) -> str:
    return digest({k: spec.get(k) for k in ('slug', 'action', 'rules', 'receipt', 'provenance', 'intakeKind')})


def execute(spec: dict, facts: dict, request_id: str, database: str | Path,
            *, lose_ack: bool = False) -> dict:
    if not isinstance(facts, dict):
        raise ValueError('Facts must be an object')
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,79}', request_id):
        raise ValueError('Invalid request identifier')
    required = {r['field'] for r in spec['rules']}
    if set(facts) - required:
        return result('blocked', 'unknown_fact')
    bound_facts = {r['field']: facts.get(r['field']) for r in spec['rules']
                   if r['phase'] == 'request'}
    fingerprint = digest({'case': spec['slug'], 'facts': bound_facts})
    with closing(connect(database)) as conn, conn:
        # The write lock makes lookup + synthetic effect one atomic operation.
        conn.execute('BEGIN IMMEDIATE')
        previous = conn.execute('SELECT * FROM requests WHERE request_id = ?', (request_id,)).fetchone()
        if previous:
            if previous['fingerprint'] != fingerprint or previous['contract_hash'] != contract_hash(spec):
                return result('conflict', 'request_identity_changed', effects=1, replay=True)
            return result(previous['status'], previous['reason'], previous['reference'], 1, True)
        failure = evaluate(spec, facts, 'request')
        if failure:
            return result('blocked', failure)
        failure = evaluate(spec, facts, 'receipt')
        status = 'pending' if failure else 'succeeded'
        reason = failure or 'verified_fixture_receipt'
        # A fixture marker, not a bank/clinic/provider-issued reference.
        reference = 'LAB-' + digest({'case': spec['slug'], 'request': request_id})[:12]
        conn.execute('INSERT INTO requests VALUES (?, ?, ?, ?, ?, ?, ?)',
                     (request_id, spec['slug'], fingerprint, status, reason, reference, contract_hash(spec)))
    if lose_ack:
        # The simulated service committed but the caller did not receive its response.
        return result('pending', 'acknowledgment_lost', effects=1)
    return result(status, reason, reference, 1)


def lookup(database: str | Path, request_id: str) -> dict:
    with closing(connect(database)) as conn:
        row = conn.execute('SELECT * FROM requests WHERE request_id = ?', (request_id,)).fetchone()
    if row is None:
        return result('unknown', 'no_local_record')
    return result(row['status'], row['reason'], row['reference'], 1, True)


def reconcile(spec: dict, facts: dict, request_id: str, database: str | Path) -> dict:
    """Lab-only receipt update, never a new action and never model-controlled."""
    with closing(connect(database)) as conn, conn:
        conn.execute('BEGIN IMMEDIATE')
        row = conn.execute('SELECT * FROM requests WHERE request_id = ?', (request_id,)).fetchone()
        if row is None:
            return result('unknown', 'no_local_record')
        if row['case_id'] != spec['slug'] or row['contract_hash'] != contract_hash(spec):
            return result('conflict', 'receipt_contract_changed', effects=1)
        failure = evaluate(spec, facts, 'receipt')
        if failure:
            return result('pending', failure, row['reference'], 1, True)
        conn.execute("UPDATE requests SET status = 'succeeded', reason = 'verified_fixture_receipt' WHERE request_id = ?", (request_id,))
        return result('succeeded', 'verified_fixture_receipt', row['reference'], 1, True)


def count_effects(database: str | Path) -> int:
    with closing(connect(database)) as conn:
        return conn.execute('SELECT COUNT(*) FROM requests').fetchone()[0]


def prove(spec: dict, database: str | Path) -> dict:
    observations = []
    intake_observations = []
    for i, fixture in enumerate(spec['variants']):
        before = count_effects(database)
        request_id = f"{spec['slug'][:50]}-v{i}"
        actual = execute(spec, fixture['facts'], request_id, database)
        expected = fixture['expected']
        observed = {k: actual[k] for k in ('status', 'reason', 'effects')}
        assert observed == expected, (fixture['name'], observed, expected)
        delta = count_effects(database) - before
        assert delta == expected['effects'], (fixture['name'], 'stored effect mismatch')
        repeat = execute(spec, fixture['facts'], request_id, database)
        assert {k: repeat[k] for k in expected} == expected
        assert count_effects(database) - before == expected['effects'], 'duplicate action on retry'
        observations.append(dict(name=fixture['name'], **observed))
        if spec.get('intakeKind'):
            # Even a refused guarded action must not suppress independent intake.
            captured = record_intake(spec, request_id, database)
            assert captured['status'] == 'recorded' and captured['effects'] == 0
            assert record_intake(spec, request_id, database)['replay'] is True
            assert lookup_intake(database, request_id)['reference'] == captured['reference']
            assert count_effects(database) - before == expected['effects']
            intake_observations.append(dict(name=fixture['name'], status=captured['status'], guardedStatus=actual['status']))
    # A lost response leaves an effect. Lookup resolves it without a second action.
    lost_id = spec['slug'][:50] + '-lost'
    lost = execute(spec, spec['facts'], lost_id, database, lose_ack=True)
    assert lost['status'] == 'pending' and lost['reference'] is None
    before = count_effects(database)
    assert lookup(database, lost_id)['status'] == 'succeeded'
    assert execute(spec, spec['facts'], lost_id, database)['replay'] is True
    assert count_effects(database) == before
    # A caller cannot reuse a committed identifier for a corrected request.
    changed = dict(spec['facts'])
    pre = next(r for r in spec['rules'] if r['phase'] == 'request')
    changed[pre['field']] = False
    assert execute(spec, changed, lost_id, database)['status'] == 'conflict'
    # Reconciliation updates only the existing synthetic row.
    for i, rule in enumerate(spec['rules']):
        if rule['phase'] != 'receipt':
            continue
        facts = dict(spec['facts'], **{rule['field']: False})
        rid = spec['slug'][:50] + f'-reconcile{i}'
        assert execute(spec, facts, rid, database)['status'] == 'pending'
        before = count_effects(database)
        assert reconcile(spec, spec['facts'], rid, database)['status'] == 'succeeded'
        assert count_effects(database) == before
    # Exercise each broken predicate against the independently stored oracle.
    killed = []
    for rule in spec['rules']:
        mutant = json.loads(json.dumps(spec))
        mutant['rules'] = [r for r in mutant['rules'] if r['field'] != rule['field']]
        fixture = next(f for f in spec['variants'] if f['name'] == rule['field'] + '-false')
        # Mutant no longer considers the deleted predicate part of the contract.
        facts = {k: v for k, v in fixture['facts'].items() if k != rule['field']}
        with tempfile.TemporaryDirectory() as tmp:
            outcome = execute(mutant, facts, 'mutant', Path(tmp) / 'ledger.sqlite')
        assert outcome['status'] != fixture['expected']['status'], 'surviving predicate deletion'
        killed.append(rule['field'])
    return dict(case=spec['slug'], fixtureHash=digest(spec), observations=observations, independentIntakes=intake_observations,
                assertions=['stored-effects', 'replay', 'lost-ack-lookup', 'changed-identity', 'receipt-reconciliation'],
                mutationsKilled=killed, limit='Synthetic evidence contract only; no model or external service exercised.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case', required=True)
    parser.add_argument('--prove', action='store_true')
    parser.add_argument('--facts', type=Path, help='Local trusted lab facts JSON; not a model input')
    parser.add_argument('--request-id', default='example-1')
    parser.add_argument('--database', type=Path, default=Path('casebook.sqlite'))
    parser.add_argument('--lookup', action='store_true')
    parser.add_argument('--reconcile', action='store_true')
    parser.add_argument('--lose-ack', action='store_true')
    parser.add_argument('--intake', action='store_true', help='Explicit independent observation/request intake for supported cases')
    parser.add_argument('--lookup-intake', action='store_true')
    args = parser.parse_args()
    spec = load_case(args.case)
    if args.prove:
        with tempfile.TemporaryDirectory() as tmp:
            output = prove(spec, Path(tmp) / 'ledger.sqlite')
    elif args.intake:
        output = record_intake(spec, args.request_id, args.database)
    elif args.lookup_intake:
        output = lookup_intake(args.database, args.request_id)
    elif args.lookup:
        output = lookup(args.database, args.request_id)
    else:
        facts = json.loads(args.facts.read_text()) if args.facts else spec['facts']
        if args.reconcile:
            output = reconcile(spec, facts, args.request_id, args.database)
        else:
            output = execute(spec, facts, args.request_id, args.database, lose_ack=args.lose_ack)
    print(json.dumps(output, indent=2))


if __name__ == '__main__':
    main()
