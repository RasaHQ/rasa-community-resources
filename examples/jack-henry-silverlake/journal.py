"""Private local fixture journal; no model tools, vendor payloads or dispatch.

Keep this owner open for the backend's lifetime. Recovery never creates a
missing database. Initialization is an explicit, new-fixture action, not a
restart or an unknown-outcome reset. A stopped-fixture audited reset and the
host/dispatcher integration are separate, unfinished source increments.
"""
from __future__ import annotations

from contextlib import contextmanager
import fcntl
import os
from pathlib import Path
import sqlite3
import threading
import uuid


class JournalRefused(Exception):
    """Redacted local failure; do not expose SQLite details to a caller."""


def _identifier(value):
    if not isinstance(value, str) or not value or len(value) > 128 or any(ord(c) < 32 for c in value):
        raise JournalRefused("invalid_fixture_identifier")
    return value


class Journal:
    """One OS-locked owner, durable pre-send markers and principal-wide holds."""

    def __init__(self, directory: Path, instance: str, *, initialize=False):
        self._thread = threading.RLock()
        self._db = None
        self._lease = None
        self._closed = False
        instance = _identifier(instance)
        directory = Path(directory).absolute()
        if directory.is_symlink() or any(p.is_symlink() for p in directory.parents):
            raise JournalRefused("unsafe_fixture_directory")
        database = directory / "journal.sqlite3"
        lease = directory / "writer.lock"
        try:
            if initialize:
                # Atomic new directory prevents repeated init from discarding a
                # journal or stale ownership metadata. Never unlink either file.
                directory.mkdir(mode=0o700, parents=False, exist_ok=False)
            if not directory.is_dir() or lease.is_symlink() or database.is_symlink():
                raise JournalRefused("fixture_recovery_required")
            self._lease = os.open(lease, (os.O_CREAT | os.O_EXCL if initialize else 0) | os.O_RDWR | os.O_NOFOLLOW, 0o600)
            fcntl.flock(self._lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
            if not initialize and not database.is_file():
                raise JournalRefused("fixture_recovery_required")
            uri = database.as_uri() + ("?mode=rwc" if initialize else "?mode=rw")
            self._db = sqlite3.connect(uri, uri=True, timeout=0, isolation_level=None, check_same_thread=False)
            self._db.execute("PRAGMA synchronous=FULL")
            self._db.execute("PRAGMA journal_mode=DELETE")
            if self._db.execute("PRAGMA quick_check").fetchall() != [("ok",)]:
                raise JournalRefused("fixture_recovery_required")
            if initialize:
                with self._transaction():
                    self._db.execute("CREATE TABLE fixture (instance TEXT PRIMARY KEY, epoch TEXT NOT NULL)")
                    self._db.execute("CREATE TABLE operations (operation TEXT PRIMARY KEY, principal TEXT NOT NULL, state TEXT NOT NULL CHECK(state IN ('pending','unknown','accepted','rejected')))")
                    self._db.execute("INSERT INTO fixture VALUES (?, ?)", (instance, uuid.uuid4().hex))
                # The directory entry, not just SQLite pages, must survive.
                for entry in (directory, directory.parent):
                    fd = os.open(entry, os.O_RDONLY)
                    try:
                        os.fsync(fd)
                    finally:
                        os.close(fd)
            rows = self._db.execute("SELECT instance, epoch FROM fixture").fetchall()
            if len(rows) != 1 or rows[0][0] != instance:
                raise JournalRefused("fixture_binding_changed")
            self.epoch = rows[0][1]
            # A process crash cannot prove whether a marked request was sent.
            with self._transaction():
                self._db.execute("UPDATE operations SET state='unknown' WHERE state='pending'")
        except (OSError, sqlite3.Error, JournalRefused):
            self.close()
            raise JournalRefused("fixture_recovery_required") from None

    @contextmanager
    def _transaction(self):
        if self._closed or self._db is None:
            raise JournalRefused("journal_closed")
        with self._thread:
            try:
                self._db.execute("BEGIN IMMEDIATE")
                yield
                self._db.execute("COMMIT")
            except Exception:
                if self._db.in_transaction:
                    self._db.execute("ROLLBACK")
                raise

    def held(self, principal):
        principal = _identifier(principal)
        with self._thread:
            if self._closed:
                raise JournalRefused("journal_closed")
            try:
                return bool(self._db.execute("SELECT 1 FROM operations WHERE principal=? AND state IN ('pending','unknown') LIMIT 1", (principal,)).fetchone())
            except sqlite3.Error:
                raise JournalRefused("fixture_recovery_required") from None

    def reserve(self, principal, operation, epoch):
        """Commit before any send; changed details/session cannot escape a hold.

        The future dispatcher must first recheck live host authority and must
        never resend a previously reserved operation, even after a known result.
        """
        principal, operation = _identifier(principal), _identifier(operation)
        try:
            with self._transaction():
                if epoch != self.epoch:
                    raise JournalRefused("fixture_epoch_changed")
                if self.held(principal):
                    raise JournalRefused("principal_held")
                self._db.execute("INSERT INTO operations VALUES (?, ?, 'pending')", (operation, principal))
        except sqlite3.Error:
            raise JournalRefused("reservation_refused") from None

    def result(self, operation, outcome):
        """Record only a definitive direct reply, or conservatively unknown.

        Unknown has no in-place clear/reconcile method. No status endpoint or
        vendor idempotency guarantee is invented by this component.
        """
        operation = _identifier(operation)
        if outcome not in {"accepted", "rejected", "unknown"}:
            raise JournalRefused("invalid_outcome")
        try:
            with self._transaction():
                changed = self._db.execute("UPDATE operations SET state=? WHERE operation=? AND state='pending'", (outcome, operation)).rowcount
                if changed != 1:
                    raise JournalRefused("operation_unavailable")
        except sqlite3.Error:
            raise JournalRefused("fixture_recovery_required") from None

    def close(self):
        with self._thread:
            if self._closed:
                return
            self._closed = True
            try:
                if self._db is not None:
                    self._db.close()
            finally:
                if self._lease is not None:
                    os.close(self._lease)
                    self._lease = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
