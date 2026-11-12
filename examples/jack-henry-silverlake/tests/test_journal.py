"""Durability and cross-process ownership controls; no SDK or vendor calls."""
from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from journal import Journal, JournalRefused


class JournalTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name).resolve() / 'fixture'
        self.journal = Journal(self.path, 'fictional-instance', initialize=True)
        self.addCleanup(self.journal.close)

    def child(self, program):
        return subprocess.run([sys.executable, '-c', program, str(self.path)],
                              env={'PYTHONPATH': str(Path(__file__).resolve().parents[1]), 'PATH': os.defpath},
                              capture_output=True, text=True, timeout=10)

    def test_marker_is_committed_before_consumer_can_send(self):
        self.journal.reserve('principal-A', 'operation-A', self.journal.epoch)
        with sqlite3.connect(self.path / 'journal.sqlite3') as reader:
            self.assertEqual(reader.execute('SELECT principal,state FROM operations').fetchall(), [('principal-A', 'pending')])
        self.assertTrue(self.journal.held('principal-A'))
        self.assertEqual(self.journal._db.execute('PRAGMA synchronous').fetchone()[0], 2)

    def test_principal_hold_covers_changed_operations_and_other_principal_works(self):
        self.journal.reserve('principal-A', 'operation-A', self.journal.epoch)
        with self.assertRaisesRegex(JournalRefused, 'principal_held'):
            self.journal.reserve('principal-A', 'changed-donor-amount-session', self.journal.epoch)
        self.journal.reserve('principal-B', 'operation-B', self.journal.epoch)
        self.assertTrue(self.journal.held('principal-B'))

    def test_unknown_survives_close_reopen_and_cannot_be_cleared_by_result(self):
        self.journal.reserve('principal-A', 'operation-A', self.journal.epoch)
        self.journal.result('operation-A', 'unknown')
        self.journal.close()
        with Journal(self.path, 'fictional-instance') as reopened:
            self.assertTrue(reopened.held('principal-A'))
            with self.assertRaisesRegex(JournalRefused, 'operation_unavailable'):
                reopened.result('operation-A', 'rejected')

    def test_known_reply_allows_new_operation_but_never_replays_old(self):
        for outcome in ('accepted', 'rejected'):
            with self.subTest(outcome=outcome):
                op = 'operation-' + outcome
                self.journal.reserve('principal-A', op, self.journal.epoch)
                self.journal.result(op, outcome)
                self.assertFalse(self.journal.held('principal-A'))
                with self.assertRaisesRegex(JournalRefused, 'reservation_refused'):
                    self.journal.reserve('principal-A', op, self.journal.epoch)

    def test_process_crash_after_marker_preserves_unknown_hold(self):
        self.journal.close()
        child = self.child('from pathlib import Path; import sys,os; from journal import Journal; j=Journal(Path(sys.argv[1]),"fictional-instance"); j.reserve("principal-A","operation-A",j.epoch); os._exit(23)')
        self.assertEqual(child.returncode, 23, child.stderr)
        with Journal(self.path, 'fictional-instance') as recovered:
            self.assertTrue(recovered.held('principal-A'))
            self.assertEqual(recovered._db.execute('SELECT state FROM operations').fetchone(), ('unknown',))

    def test_live_os_lock_wins_over_misleading_stale_pid_metadata(self):
        (self.path / 'writer.lock').write_text('pid=999999999\n')
        child = self.child('from pathlib import Path; import sys; from journal import Journal,JournalRefused;\ntry: Journal(Path(sys.argv[1]),"fictional-instance")\nexcept JournalRefused: sys.exit(19)\nsys.exit(0)')
        self.assertEqual(child.returncode, 19, child.stderr)
        self.journal.reserve('principal-A', 'operation-A', self.journal.epoch)

    def test_concurrent_thread_reservations_have_one_winner(self):
        def reserve(number):
            try:
                self.journal.reserve('principal-A', 'operation-' + str(number), self.journal.epoch)
                return True
            except JournalRefused:
                return False
        with ThreadPoolExecutor(max_workers=8) as executor:
            self.assertEqual(sum(executor.map(reserve, range(16))), 1)

    def test_missing_database_is_not_reinitialized(self):
        self.journal.close()
        (self.path / 'journal.sqlite3').unlink()
        with self.assertRaisesRegex(JournalRefused, 'fixture_recovery_required'):
            Journal(self.path, 'fictional-instance')
        self.assertFalse((self.path / 'journal.sqlite3').exists())

    def test_missing_lease_is_not_recreated_on_recovery(self):
        self.journal.close()
        (self.path / 'writer.lock').unlink()
        with self.assertRaisesRegex(JournalRefused, 'fixture_recovery_required'):
            Journal(self.path, 'fictional-instance')
        self.assertFalse((self.path / 'writer.lock').exists())

    def test_corrupt_database_preserved_and_refused(self):
        self.journal.close()
        damaged = b'authored corrupt database control'
        (self.path / 'journal.sqlite3').write_bytes(damaged)
        with self.assertRaisesRegex(JournalRefused, 'fixture_recovery_required'):
            Journal(self.path, 'fictional-instance')
        self.assertEqual((self.path / 'journal.sqlite3').read_bytes(), damaged)

    def test_repeat_initialization_and_binding_change_refuse(self):
        self.journal.reserve('principal-A', 'operation-A', self.journal.epoch)
        self.journal.close()
        with self.assertRaises(JournalRefused):
            Journal(self.path, 'fictional-instance', initialize=True)
        with self.assertRaises(JournalRefused):
            Journal(self.path, 'different-instance')
        with Journal(self.path, 'fictional-instance') as recovered:
            self.assertTrue(recovered.held('principal-A'))

    def test_wrong_epoch_refuses_before_marker(self):
        with self.assertRaisesRegex(JournalRefused, 'fixture_epoch_changed'):
            self.journal.reserve('principal-A', 'operation-A', 'previous-epoch')
        self.assertFalse(self.journal.held('principal-A'))

    def test_commit_failure_rolls_back_and_refuses_no_dispatch(self):
        # A second connection deliberately holds SQLite's write lock. The
        # service lease remains ours; reserve still must refuse before a send.
        other = sqlite3.connect(self.path / 'journal.sqlite3', isolation_level=None)
        self.addCleanup(other.close)
        other.execute('BEGIN IMMEDIATE')
        with self.assertRaises(JournalRefused):
            self.journal.reserve('principal-A', 'operation-A', self.journal.epoch)
        other.execute('ROLLBACK')
        self.assertFalse(self.journal.held('principal-A'))

    def test_initial_directory_fsync_failure_does_not_silently_reinitialize(self):
        path = Path(self.tmp.name).resolve() / 'failed-init'
        with patch('journal.os.fsync', side_effect=OSError('authored persistence failure')):
            with self.assertRaises(JournalRefused):
                Journal(path, 'fictional-instance', initialize=True)
        with self.assertRaises(JournalRefused):
            Journal(path, 'fictional-instance', initialize=True)

    def test_symlink_path_and_closed_owner_refuse(self):
        alias = Path(self.tmp.name).resolve() / 'alias'
        alias.symlink_to(self.path, target_is_directory=True)
        with self.assertRaises(JournalRefused):
            Journal(alias, 'fictional-instance')
        self.journal.close()
        with self.assertRaises(JournalRefused):
            self.journal.reserve('principal-A', 'operation-A', self.journal.epoch)


if __name__ == '__main__':
    unittest.main()
