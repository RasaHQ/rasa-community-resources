# SPDX-License-Identifier: MIT
"""Conservative local accounting for the optional manual trial. Mock mode never uses it.

This is a local ledger of an operator-attested allowance, not a read of Fiserv's
quota. There is no provider endpoint for remaining usage, so manual dispatch is
available only while an operator-written budget attestation is fresh, matches
this trial, period, organization and runner, and has capacity left. Every
attempt, including a timeout or a 429, is charged before it is sent. Counts are
never replenished by a restart, a mode switch, a fixture reset or a new budget
id for the same binding. Clock rollback or an unreadable ledger fails closed.
"""
from __future__ import annotations

import fcntl
import hashlib
import json
import math
from pathlib import Path
import sqlite3
import time

ORGANIZATION = "999990301"
MAX_PER_RUN = 3
ROLLING_SECONDS = 60
ROLLING_LIMIT = 9
MIN_SPACING = 7.0
FRESH_SECONDS = 300
MAX_REMAINING = 1000
FIELDS = ("budget_id", "trial_id", "period_id", "organization_id", "runner_id",
          "operator", "as_of", "expires_at", "remaining_core_attempts", "basis")


class QuotaRefused(Exception):
    """A closed reason. Nothing was sent."""


class Ledger:
    def __init__(self, path: Path, *, clock=time.time):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path, self.clock = path, clock
        self._lock_file = open(path.with_suffix(".lock"), "a+")
        try:
            fcntl.flock(self._lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self._lock_file.close()
            raise QuotaRefused("ledger_in_use") from None
        try:
            self._db = sqlite3.connect(path, isolation_level=None, check_same_thread=False)
            self._db.execute("PRAGMA synchronous=FULL")
            self._db.executescript("""
                CREATE TABLE IF NOT EXISTS seen(id INTEGER PRIMARY KEY CHECK(id=1), at REAL);
                CREATE TABLE IF NOT EXISTS allowance(
                    trial_id TEXT, period_id TEXT, org TEXT, runner TEXT,
                    remaining INTEGER, held INTEGER, budget_id TEXT, as_of REAL, expires_at REAL,
                    blocked INTEGER DEFAULT 0, generation INTEGER DEFAULT 1,
                    PRIMARY KEY(trial_id, period_id, org, runner));
                CREATE TABLE IF NOT EXISTS budget(budget_id TEXT PRIMARY KEY, sha256 TEXT);
                CREATE TABLE IF NOT EXISTS reservation(
                    id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT,
                    trial_id TEXT, period_id TEXT, org TEXT, runner TEXT,
                    held INTEGER, used INTEGER DEFAULT 0, generation INTEGER);
                CREATE TABLE IF NOT EXISTS attempt(at REAL, kind TEXT, run_id TEXT,
                    trial_id TEXT, period_id TEXT, org TEXT, runner TEXT);
                CREATE TABLE IF NOT EXISTS release_audit(at REAL, reservation INTEGER, released INTEGER, reason TEXT);
            """)
        except sqlite3.Error:
            self._lock_file.close()
            raise QuotaRefused("ledger_unreadable") from None

    def close(self):
        self._db.close()
        self._lock_file.close()

    # -- clock ---------------------------------------------------------------
    def _now(self) -> float:
        now = self.clock()
        row = self._db.execute("SELECT at FROM seen").fetchone()
        if row and now < row[0]:
            raise QuotaRefused("clock_rollback")
        self._db.execute("INSERT INTO seen VALUES(1, ?) ON CONFLICT(id) DO UPDATE SET at=excluded.at", (now,))
        return now

    def _transaction(self):
        self._db.execute("BEGIN IMMEDIATE")

    # -- attestation -----------------------------------------------------------
    def import_budget(self, raw: bytes, *, approved_runner: str) -> dict:
        """Import an operator-written attestation. Only a trusted local command calls this."""
        def _reject_constant(name):
            raise ValueError(name)  # NaN, Infinity and -Infinity are not JSON numbers

        try:
            record = json.loads(raw, parse_constant=_reject_constant)
        except (ValueError, TypeError, RecursionError):
            raise QuotaRefused("budget_invalid") from None
        if (not isinstance(record, dict) or set(record) != set(FIELDS)
                or any(not isinstance(record[name], str) or not record[name].strip()
                       for name in ("budget_id", "trial_id", "period_id", "organization_id",
                                    "runner_id", "operator", "basis"))
                or type(record["remaining_core_attempts"]) is not int
                or isinstance(record["as_of"], bool) or isinstance(record["expires_at"], bool)
                or not isinstance(record["as_of"], (int, float))
                or not isinstance(record["expires_at"], (int, float))
                or not math.isfinite(record["as_of"]) or not math.isfinite(record["expires_at"])
                or not 0 <= record["remaining_core_attempts"] <= MAX_REMAINING):
            raise QuotaRefused("budget_invalid")
        if record["organization_id"] != ORGANIZATION or record["runner_id"] != approved_runner:
            raise QuotaRefused("budget_mismatch")
        digest = hashlib.sha256(raw).hexdigest()
        self._transaction()
        try:
            now = self._now()
            if (record["as_of"] > now or now - record["as_of"] >= FRESH_SECONDS
                    or record["expires_at"] <= now or record["expires_at"] > record["as_of"] + FRESH_SECONDS):
                raise QuotaRefused("budget_not_fresh")
            known = self._db.execute("SELECT sha256 FROM budget WHERE budget_id=?",
                                     (record["budget_id"],)).fetchone()
            if known is not None:
                # The same id never replenishes; altered bytes under it refuse.
                raise QuotaRefused("budget_replay" if known[0] == digest else "budget_altered")
            key = (record["trial_id"], record["period_id"], record["organization_id"], record["runner_id"])
            row = self._db.execute(
                "SELECT remaining, held, as_of FROM allowance WHERE trial_id=? AND period_id=? AND org=? AND runner=?",
                key).fetchone()
            if row is None:
                remaining, held, blocked = record["remaining_core_attempts"], 0, 0
                self._db.execute("INSERT INTO allowance VALUES(?,?,?,?,?,?,?,?,?,?,1)",
                                 (*key, remaining, held, record["budget_id"], record["as_of"],
                                  record["expires_at"], blocked))
            else:
                current, held, old_as_of = row
                if record["as_of"] <= old_as_of:
                    raise QuotaRefused("budget_older")
                charged = self._db.execute(
                    "SELECT count(*) FROM attempt WHERE kind='core' AND at>? AND trial_id=? AND period_id=? "
                    "AND org=? AND runner=?", (record["as_of"], *key)).fetchone()[0]
                # A renewal can refresh validity or lower the count, never replenish.
                remaining = min(current, max(0, record["remaining_core_attempts"] - charged))
                blocked = 1 if remaining < held else 0
                self._db.execute(
                    "UPDATE allowance SET remaining=?, budget_id=?, as_of=?, expires_at=?, blocked=?, "
                    "generation=generation+1 WHERE trial_id=? AND period_id=? AND org=? AND runner=?",
                    (remaining, record["budget_id"], record["as_of"], record["expires_at"], blocked, *key))
            self._db.execute("INSERT INTO budget VALUES(?,?)", (record["budget_id"], digest))
            self._db.execute("COMMIT")
        except BaseException:
            self._db.execute("ROLLBACK")
            raise
        return {"remaining": remaining, "held": held, "blocked": bool(blocked)}

    # -- reservation and attempts ----------------------------------------------
    def _active(self, key, now):
        row = self._db.execute(
            "SELECT remaining, held, expires_at, blocked, generation FROM allowance "
            "WHERE trial_id=? AND period_id=? AND org=? AND runner=?", key).fetchone()
        if row is None:
            raise QuotaRefused("no_budget")
        remaining, held, expires, blocked, generation = row
        if blocked:
            raise QuotaRefused("budget_blocked")
        if expires <= now:
            raise QuotaRefused("budget_expired")
        return remaining, held, generation

    def reserve(self, run_id: str, key: tuple, count: int = MAX_PER_RUN) -> int:
        if type(count) is not int or not 1 <= count <= MAX_PER_RUN:
            raise QuotaRefused("invalid_count")
        self._transaction()
        try:
            now = self._now()
            remaining, held, generation = self._active(key, now)
            if remaining - held < count:
                raise QuotaRefused("budget_exhausted")
            self._db.execute("UPDATE allowance SET held=held+? WHERE trial_id=? AND period_id=? AND org=? AND runner=?",
                             (count, *key))
            cursor = self._db.execute(
                "INSERT INTO reservation(run_id, trial_id, period_id, org, runner, held, generation) VALUES(?,?,?,?,?,?,?)",
                (run_id, *key, count, generation))
            self._db.execute("COMMIT")
            return cursor.lastrowid
        except BaseException:
            self._db.execute("ROLLBACK")
            raise

    def charge_core_attempt(self, reservation: int) -> None:
        """Immediately before a physical core call: consume one held attempt, once."""
        self._transaction()
        try:
            now = self._now()
            row = self._db.execute(
                "SELECT run_id, trial_id, period_id, org, runner, held, used FROM reservation WHERE id=?",
                (reservation,)).fetchone()
            if row is None or row[5] <= 0:
                raise QuotaRefused("reservation_unavailable")
            run_id, key, held, used = row[0], tuple(row[1:5]), row[5], row[6]
            remaining, total_held, _ = self._active(key, now)  # revalidates the CURRENT allowance
            if used >= MAX_PER_RUN:
                raise QuotaRefused("per_run_limit")
            window = self._db.execute("SELECT count(*), max(at) FROM attempt WHERE kind='core' AND at>?",
                                      (now - ROLLING_SECONDS,)).fetchone()
            if window[0] >= ROLLING_LIMIT:
                raise QuotaRefused("rolling_window_limit")
            last = self._db.execute("SELECT max(at) FROM attempt WHERE kind='core'").fetchone()[0]
            if last is not None and now - last < MIN_SPACING:
                raise QuotaRefused("spacing")
            if remaining <= 0 or total_held <= 0:
                raise QuotaRefused("budget_exhausted")
            self._db.execute("UPDATE reservation SET held=held-1, used=used+1 WHERE id=?", (reservation,))
            self._db.execute("UPDATE allowance SET held=held-1, remaining=remaining-1 "
                             "WHERE trial_id=? AND period_id=? AND org=? AND runner=?", key)
            self._db.execute("INSERT INTO attempt VALUES(?,?,?,?,?,?,?)", (now, "core", run_id, *key))
            self._db.execute("COMMIT")
        except BaseException:
            self._db.execute("ROLLBACK")
            raise

    def charge_token_attempt(self, run_id: str) -> None:
        """At most one token attempt per run, no refresh."""
        self._transaction()
        try:
            now = self._now()
            if self._db.execute("SELECT 1 FROM attempt WHERE kind='token' AND run_id=?", (run_id,)).fetchone():
                raise QuotaRefused("token_limit")
            self._db.execute("INSERT INTO attempt VALUES(?,?,?,?,?,?,?)", (now, "token", run_id, "", "", "", ""))
            self._db.execute("COMMIT")
        except BaseException:
            self._db.execute("ROLLBACK")
            raise

    def seconds_until_core(self) -> float:
        """How long until the spacing rule allows the next core attempt (read only)."""
        last = self._db.execute("SELECT max(at) FROM attempt WHERE kind='core'").fetchone()[0]
        if last is None:
            return 0.0
        return max(0.0, MIN_SPACING - (self.clock() - last))

    def release_unused(self, reservation: int, reason: str) -> int:
        """Audited safe stop: return a run's unused held attempts. Never sends, never replenishes spent ones."""
        if not isinstance(reason, str) or not reason.strip():
            raise QuotaRefused("reason_required")
        self._transaction()
        try:
            now = self._now()
            row = self._db.execute("SELECT trial_id, period_id, org, runner, held FROM reservation WHERE id=?",
                                   (reservation,)).fetchone()
            if row is None:
                raise QuotaRefused("reservation_unavailable")
            key, held = tuple(row[:4]), row[4]
            if held > 0:
                self._db.execute("UPDATE reservation SET held=0 WHERE id=?", (reservation,))
                self._db.execute("UPDATE allowance SET held=held-? WHERE trial_id=? AND period_id=? AND org=? "
                                 "AND runner=?", (held, *key))
                self._db.execute("INSERT INTO release_audit VALUES(?,?,?,?)", (now, reservation, held, reason.strip()[:200]))
            self._db.execute("COMMIT")
            return held
        except BaseException:
            self._db.execute("ROLLBACK")
            raise

    def snapshot(self, key: tuple) -> dict:
        row = self._db.execute("SELECT remaining, held, blocked FROM allowance WHERE trial_id=? AND period_id=? "
                               "AND org=? AND runner=?", key).fetchone()
        return {"remaining": row[0], "held": row[1], "blocked": bool(row[2])} if row else {}
