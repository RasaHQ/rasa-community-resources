"""Fixed-byte staging controls, not a new live run."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from briefing import factory_receiver as receiver

FIXTURE = Path(__file__).parent / 'fixtures/f7-accepted-run'
TARGET = 'a' * 40  # Deliberately synthetic owner-declared target for offline controls.


def stage_fixture(directory):
    source = directory / 'source'
    shutil.copytree(FIXTURE, source)
    target = directory / 'received'
    record = receiver.stage_accepted_run(source, target, source_head=receiver.SOURCE_HEAD, target_head=TARGET)
    return source, target, record


class FactoryReceiverTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.source = self.root / 'source'
        shutil.copytree(FIXTURE, self.source)
        self.target = self.root / 'received'

    def stage(self):
        return receiver.stage_accepted_run(self.source, self.target,
            source_head=receiver.SOURCE_HEAD, target_head=TARGET)

    def test_stages_exact_files_without_altering_the_source_or_claiming_restart(self):
        before = {str(p.relative_to(self.source)): hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in self.source.rglob('*') if p.is_file()}
        hook = receiver.make_receiver_hook(self.target, source_head=receiver.SOURCE_HEAD, target_head=TARGET)
        record = hook(self.source)
        self.assertEqual(record['status'], 'NOT_RECORDED')
        self.assertEqual(record['reason_code'], 'candidate_staged')
        self.assertIsNone(record['baseline_head'])
        self.assertIsNone(record['integrated_head'])
        receipt = json.loads((self.target / 'staging.json').read_text())
        self.assertEqual(receipt['product_acceptance'], 'NOT_RUN')
        self.assertEqual(receipt['source_head'], receiver.SOURCE_HEAD)
        self.assertEqual(receipt['target_head'], TARGET)
        for name in receiver.FILES:
            self.assertEqual((self.target / 'candidate' / name).read_bytes(),
                             (self.source / 'candidate' / name).read_bytes())
        after = {str(p.relative_to(self.source)): hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in self.source.rglob('*') if p.is_file()}
        self.assertEqual(before, after)
        self.assertFalse((self.source / 'integration.json').exists())
        with self.assertRaises(receiver.ReceiverRefused):
            hook(self.source)

    def test_refuses_unfinished_native_or_false_accept_before_creating_evidence(self):
        controls = [('native.json', 'status', 'incomplete'), ('native.json', 'ok', False),
                    ('native.json', 'ok', 1), ('console.json', 'mode', 'SCRIPTED'),
                    ('console.json', 'state', 'ERROR'),
                    ('verification/decision.json', 'decision', 'REJECT'),
                    ('verification/decision.json', 'candidate_digest', '0' * 64),
                    ('verification/decision.json', 'task', 'B-limit-currencies'),
                    ('verification/decision.json', 'acceptance_sha256', '0' * 64),
                    ('verification/decision.json', 'support_sha256', {}),
                    ('verification/decision.json', 'checks', [{'name': 'protected acceptance', 'passed': False}]),
                    ('verification/decision.json', 'checks', [{'name': 'protected acceptance', 'passed': False},
                                                            {'name': 'protected acceptance', 'passed': True}])]
        for filename, key, value in controls:
            with self.subTest(filename=filename, key=key, value=value):
                path = self.source / filename
                original = path.read_bytes()
                record = json.loads(original)
                record[key] = value
                path.write_text(json.dumps(record))
                try:
                    with self.assertRaises(receiver.ReceiverRefused):
                        self.stage()
                    self.assertFalse(self.target.exists())
                finally:
                    path.write_bytes(original)

    def test_task_bytes_and_duplicate_json_keys_are_not_trusted(self):
        task = self.source / 'task/a6-market-watchlist.json'
        original = task.read_bytes()
        task.write_bytes(original + b'\n')
        with self.assertRaises(receiver.ReceiverRefused):
            self.stage()
        task.write_bytes(original)
        (self.source / 'native.json').write_text('{"status":"failed","status":"completed","ok":true}')
        with self.assertRaisesRegex(receiver.ReceiverRefused, 'duplicate_evidence_key'):
            self.stage()
        self.assertFalse(self.target.exists())

    def test_receipt_identifies_exact_self_attested_evidence_bytes(self):
        first = self.stage()
        expected = {name: hashlib.sha256((self.source / name).read_bytes()).hexdigest()
                    for name in receiver.EVIDENCE_FILES}
        self.assertEqual(first['evidence_sha256'], expected)
        self.assertEqual(first['evidence_basis'], 'self_attested_records_not_authenticated')
        native = self.source / 'native.json'
        native.write_bytes(native.read_bytes() + b'\n')  # Same JSON fields, different input record.
        second = receiver.stage_accepted_run(self.source, self.root / 'second-received',
            source_head=receiver.SOURCE_HEAD, target_head=TARGET)
        self.assertNotEqual(first['evidence_sha256']['native.json'], second['evidence_sha256']['native.json'])
        self.assertEqual(first['candidate_digest'], second['candidate_digest'])
        for name in receiver.EVIDENCE_FILES[1:]:
            self.assertEqual(first['evidence_sha256'][name], second['evidence_sha256'][name])

    def test_hardlink_on_allowed_candidate_with_identical_bytes_is_refused_by_link_guard(self):
        path = self.source / 'candidate' / receiver.FILES[0]
        original = path.read_bytes()
        outside = self.root / 'identical-market.py'
        outside.write_bytes(original)
        path.unlink()
        os.link(outside, path)
        with self.assertRaisesRegex(receiver.ReceiverRefused, '^candidate_paths_mismatch$'):
            self.stage()
        self.assertFalse(self.target.exists())
        self.assertEqual(outside.read_bytes(), original)

    def test_hardlink_on_allowed_metadata_with_valid_json_is_refused_by_read_guard(self):
        path = self.source / 'native.json'
        original = path.read_bytes()
        outside = self.root / 'identical-native.json'
        outside.write_bytes(original)
        path.unlink()
        os.link(outside, path)
        with self.assertRaisesRegex(receiver.ReceiverRefused, '^regular_unlinked_evidence_required$'):
            self.stage()
        self.assertFalse(self.target.exists())

    def test_fifo_on_allowed_candidate_path_is_refused_before_reading_or_hashing(self):
        path = self.source / 'candidate' / receiver.FILES[0]
        path.unlink()
        os.mkfifo(path)
        with self.assertRaisesRegex(receiver.ReceiverRefused, '^candidate_paths_mismatch$'):
            self.stage()
        self.assertFalse(self.target.exists())

    def test_target_inside_source_is_refused_without_mutating_source_tree(self):
        target = self.source / 'received'
        before = sorted(str(p.relative_to(self.source)) for p in self.source.rglob('*'))
        with self.assertRaisesRegex(receiver.ReceiverRefused, '^new_separate_receiving_directory_required$'):
            receiver.stage_accepted_run(self.source, target, source_head=receiver.SOURCE_HEAD, target_head=TARGET)
        self.assertFalse(target.exists())
        self.assertEqual(before, sorted(str(p.relative_to(self.source)) for p in self.source.rglob('*')))

    def test_metadata_64k_limit_accepts_boundary_and_refuses_one_more_byte(self):
        path = self.source / 'native.json'
        original = path.read_bytes()
        path.write_bytes(original + b' ' * (65536 - len(original)))
        self.stage()  # Padded but valid JSON at the exact boundary.
        shutil.rmtree(self.target)
        path.write_bytes(path.read_bytes() + b' ')
        with self.assertRaisesRegex(receiver.ReceiverRefused, '^evidence_size_limit$'):
            self.stage()
        self.assertFalse(self.target.exists())

    def test_files_supplied_must_match_the_exact_candidate_allowlist(self):
        path = self.source / 'verification/decision.json'
        data = json.loads(path.read_text())
        data['files_supplied'] = [receiver.FILES[0]]
        path.write_text(json.dumps(data))
        with self.assertRaisesRegex(receiver.ReceiverRefused, '^protected_task_or_decision_mismatch$'):
            self.stage()
        self.assertFalse(self.target.exists())

    def test_console_task_hash_must_match_the_exact_task_bytes(self):
        path = self.source / 'console.json'
        data = json.loads(path.read_text())
        data['task_sha256'] = '0' * 64
        path.write_text(json.dumps(data))
        with self.assertRaisesRegex(receiver.ReceiverRefused, '^protected_task_or_decision_mismatch$'):
            self.stage()
        self.assertFalse(self.target.exists())

    def test_non_list_protected_checks_are_refused(self):
        path = self.source / 'verification/decision.json'
        data = json.loads(path.read_text())
        for checks in (None, {'name': 'protected acceptance', 'passed': True}, 'protected acceptance'):
            with self.subTest(checks=checks):
                data['checks'] = checks
                path.write_text(json.dumps(data))
                with self.assertRaisesRegex(receiver.ReceiverRefused, '^protected_acceptance_required$'):
                    self.stage()
                self.assertFalse(self.target.exists())

    def test_extra_paths_links_and_special_files_are_refused(self):
        product = self.source / 'candidate/product'
        outside = self.root / 'outside'
        outside.write_text('must remain unchanged')
        for kind in ('extra', 'symlink', 'hardlink', 'fifo'):
            with self.subTest(kind=kind):
                path = product / 'unknown.py'
                if kind == 'extra':
                    path.write_text('raise AssertionError("never execute candidate commands")')
                elif kind == 'symlink':
                    path.symlink_to(outside)
                elif kind == 'hardlink':
                    os.link(outside, path)
                else:
                    os.mkfifo(path)
                try:
                    with self.assertRaises(receiver.ReceiverRefused):
                        self.stage()
                finally:
                    path.unlink()
        market = product / 'briefing/market_card.py'
        market.unlink()
        market.symlink_to(outside)
        with self.assertRaises(receiver.ReceiverRefused):
            self.stage()
        self.assertEqual(outside.read_text(), 'must remain unchanged')
        self.assertFalse(self.target.exists())

    def test_staging_metadata_links_and_invalid_heads_are_refused(self):
        native = self.source / 'native.json'
        original = native.read_bytes()
        outside = self.root / 'native-copy.json'
        outside.write_bytes(original)
        native.unlink()
        native.symlink_to(outside)
        with self.assertRaises(receiver.ReceiverRefused):
            self.stage()
        for source, target in [('0' * 40, TARGET), (receiver.SOURCE_HEAD, '../not-a-head')]:
            with self.assertRaises(receiver.ReceiverRefused):
                receiver.stage_accepted_run(self.source, self.target, source_head=source, target_head=target)
        self.assertFalse(self.target.exists())

    def test_load_checks_fixed_bytes_and_receipt_before_executing_only_the_reviewed_module(self):
        self.stage()
        market = receiver.load_accepted_market(self.target)
        sentinel = object()
        calls = []
        class Sources:
            def market(self, currencies):
                calls.append(currencies)
                return sentinel
        self.assertIs(market(Sources(), ('USD', 'GBP')), sentinel)
        self.assertEqual(calls, [('USD', 'GBP')])
        self.assertNotIn('briefing.market_card', sys.modules)
        receipt = self.target / 'staging.json'
        original = receipt.read_bytes()
        for change in ({'product_acceptance': 'APPLIED_RESTARTED'}, {'module': 'untrusted.py'},
                       {'candidate_digest': '0' * 64}, {'target_head': None},
                       {'evidence_sha256': {}}, {'evidence_basis': 'authenticated-run'},
                       {'evidence_sha256': {name: '0' * 64 for name in receiver.EVIDENCE_FILES}},
                       {'evidence_sha256': {name: 'not-a-sha256' for name in receiver.EVIDENCE_FILES}}):
            data = json.loads(original)
            data.update(change)
            receipt.write_text(json.dumps(data))
            with self.assertRaises(receiver.ReceiverRefused):
                receiver.load_accepted_market(self.target)
        receipt.write_bytes(original)
        marker = self.root / 'candidate-must-not-execute'
        (self.target / 'candidate' / receiver.FILES[0]).write_text(
            'from pathlib import Path\nPath(' + repr(str(marker)) + ').touch()\n')
        with self.assertRaises(receiver.ReceiverRefused):
            receiver.load_accepted_market(self.target)
        self.assertFalse(marker.exists())


if __name__ == '__main__':
    unittest.main()
