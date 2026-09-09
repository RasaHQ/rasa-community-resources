"""Counterexamples test the teaching contract; no language model is involved."""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from casebook import ROOT, count_effects, execute, load_case, lookup, prove, reconcile


class CasebookTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.database = Path(self.tmp.name) / 'ledger.sqlite'
        self.spec = load_case('contextual-handoff')

    def test_all_authored_oracles_and_mutations(self):
        cases = sorted((ROOT / 'examples').glob('*.json'))
        self.assertEqual(len(cases), 62)
        for path in cases:
            with self.subTest(case=path.stem):
                outcome = prove(load_case(path.stem), Path(self.tmp.name) / f'{path.stem}.sqlite')
                self.assertEqual(len(outcome['observations']), 10)
                self.assertEqual(len(outcome['mutationsKilled']), 3)

    def test_concurrent_retries_persist_exactly_one_synthetic_effect(self):
        def request(_):
            return execute(self.spec, self.spec['facts'], 'same-request', self.database)
        with ThreadPoolExecutor(max_workers=8) as workers:
            outcomes = list(workers.map(request, range(32)))
        self.assertEqual(count_effects(self.database), 1)
        self.assertEqual(len({r['reference'] for r in outcomes}), 1)
        self.assertEqual(sum(not r['replay'] for r in outcomes), 1)
        # A separate connection sees the result (not process-local memory).
        self.assertEqual(lookup(self.database, 'same-request')['status'], 'succeeded')

    def test_changed_case_or_revision_cannot_reuse_committed_identity(self):
        execute(self.spec, self.spec['facts'], 'request-1', self.database)
        other = load_case('banking-transfer')
        self.assertEqual(execute(other, other['facts'], 'request-1', self.database)['status'], 'conflict')
        changed = json.loads(json.dumps(self.spec))
        changed['provenance']['revision'] = 'changed'
        self.assertEqual(execute(changed, changed['facts'], 'request-1', self.database)['status'], 'conflict')
        self.assertEqual(reconcile(changed, changed['facts'], 'request-1', self.database)['status'], 'conflict')
        self.assertEqual(count_effects(self.database), 1)

    def test_missing_is_unknown_and_reconciliation_cannot_create_an_action(self):
        self.assertEqual(lookup(self.database, 'absent')['status'], 'unknown')
        self.assertEqual(reconcile(self.spec, self.spec['facts'], 'absent', self.database)['status'], 'unknown')
        self.assertEqual(count_effects(self.database), 0)

    def test_arbitrary_keys_and_truthy_values_do_not_grant_authority(self):
        self.assertEqual(execute(self.spec, dict(self.spec['facts'], admin=True), 'bad-key', self.database)['reason'], 'unknown_fact')
        for value in ('true', 1, [], {}, None):
            facts = dict(self.spec['facts'], redacted_summary=value)
            self.assertEqual(execute(self.spec, facts, 'bad-value', self.database)['status'], 'blocked')
        self.assertEqual(count_effects(self.database), 0)

    def test_receipt_failure_never_means_no_action(self):
        facts = dict(self.spec['facts'], desk_acknowledged=False)
        self.assertEqual(execute(self.spec, facts, 'pending', self.database)['status'], 'pending')
        self.assertEqual(count_effects(self.database), 1)
        self.assertEqual(reconcile(self.spec, facts, 'pending', self.database)['status'], 'pending')
        self.assertEqual(reconcile(self.spec, self.spec['facts'], 'pending', self.database)['status'], 'succeeded')
        self.assertEqual(count_effects(self.database), 1)

    def test_path_and_identifier_validation(self):
        for slug in ('../banking-transfer', '', '/etc/passwd', 'banking-transfer.json', 'not-a-case'):
            with self.assertRaises(ValueError):
                load_case(slug)
        with self.assertRaises(ValueError):
            execute(self.spec, self.spec['facts'], '../unsafe', self.database)


if __name__ == '__main__':
    unittest.main()
