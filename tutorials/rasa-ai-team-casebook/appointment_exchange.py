"""Synthetic single-database scheduling service for a conversation-design lab.

No Rasa runtime or external scheduler is involved. The old booking, held slot
and request receipt share one SQLite transaction. An HTTP API made from two
unrelated calls would need its own supported recovery procedure.
"""
import hashlib
import json
import sqlite3
from contextlib import contextmanager


class LostReply(ConnectionError):
    """The service committed, but its caller did not receive the receipt."""


class Scheduler:
    def __init__(self, path):
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS bookings (
                id TEXT PRIMARY KEY, customer TEXT NOT NULL, slot TEXT NOT NULL,
                revision INTEGER NOT NULL, active INTEGER NOT NULL);
            CREATE UNIQUE INDEX IF NOT EXISTS occupied_slot
                ON bookings(slot) WHERE active = 1;
            CREATE TABLE IF NOT EXISTS holds (
                id TEXT PRIMARY KEY, customer TEXT NOT NULL, slot TEXT NOT NULL,
                capability TEXT NOT NULL, expires INTEGER NOT NULL,
                consumed INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS receipts (
                request_key TEXT PRIMARY KEY, payload_hash TEXT NOT NULL,
                receipt TEXT NOT NULL);
        """)

    def close(self):
        self.db.close()

    @contextmanager
    def transaction(self):
        self.db.execute("BEGIN IMMEDIATE")
        try:
            yield
            self.db.commit()
        except BaseException:
            self.db.rollback()
            raise

    def seed(self):
        with self.transaction():
            self.db.execute("INSERT INTO bookings VALUES (?, ?, ?, ?, ?)",
                            ("visit-1", "customer-1", "Tuesday 10:00", 1, 1))

    def hold(self, hold_id, customer, slot, capability, expires, now):
        with self.transaction():
            if expires <= now:
                raise ValueError("hold must expire in the future")
            occupied = self.db.execute(
                "SELECT 1 FROM bookings WHERE slot=? AND active=1", (slot,)
            ).fetchone()
            held = self.db.execute(
                "SELECT 1 FROM holds WHERE slot=? AND consumed=0 AND expires>?",
                (slot, now),
            ).fetchone()
            if occupied or held:
                raise ValueError("slot unavailable")
            self.db.execute("INSERT INTO holds VALUES (?, ?, ?, ?, ?, 0)",
                            (hold_id, customer, slot, capability, expires))

    def lookup(self, request_key):
        row = self.db.execute("SELECT receipt FROM receipts WHERE request_key=?",
                              (request_key,)).fetchone()
        return json.loads(row[0]) if row else {"status": "unknown"}

    def active(self):
        return [dict(row) for row in self.db.execute(
            "SELECT * FROM bookings WHERE active=1 ORDER BY id")]

    def exchange(self, request_key, old_id, revision, hold_id, customer,
                 confirmed_capability, now, fail_at=None):
        # Time and fault injection are test inputs, not parts of the user's choice.
        payload = [old_id, revision, hold_id, customer, confirmed_capability]
        fingerprint = hashlib.sha256(json.dumps(payload).encode()).hexdigest()
        with self.transaction():
            previous = self.db.execute("SELECT * FROM receipts WHERE request_key=?",
                                       (request_key,)).fetchone()
            if previous:
                if previous["payload_hash"] != fingerprint:
                    return {"status": "refused", "reason": "request_changed"}
                return {**json.loads(previous["receipt"]), "replayed": True}
            old = self.db.execute("SELECT * FROM bookings WHERE id=?", (old_id,)).fetchone()
            hold = self.db.execute("SELECT * FROM holds WHERE id=?", (hold_id,)).fetchone()
            if not old or old["customer"] != customer or not old["active"]:
                return {"status": "refused", "reason": "old_booking_unavailable"}
            if old["revision"] != revision:
                return {"status": "refused", "reason": "booking_changed"}
            if not hold or hold["customer"] != customer or hold["consumed"]:
                return {"status": "refused", "reason": "hold_unavailable"}
            if hold["expires"] <= now:
                return {"status": "refused", "reason": "hold_expired"}
            if hold["capability"] != confirmed_capability:
                return {"status": "refused", "reason": "requirements_changed"}
            self.db.execute("UPDATE bookings SET active=0, revision=revision+1 WHERE id=?",
                            (old_id,))
            if fail_at == "after_old_release":
                raise RuntimeError("injected failure inside transaction")
            new_id = "from-hold-" + hold_id
            self.db.execute("INSERT INTO bookings VALUES (?, ?, ?, 1, 1)",
                            (new_id, customer, hold["slot"]))
            self.db.execute("UPDATE holds SET consumed=1 WHERE id=?", (hold_id,))
            receipt = {"status": "succeeded", "oldBooking": old_id,
                       "newBooking": new_id, "slot": hold["slot"]}
            self.db.execute("INSERT INTO receipts VALUES (?, ?, ?)",
                            (request_key, fingerprint, json.dumps(receipt, sort_keys=True)))
        if fail_at == "after_commit":
            raise LostReply("reply lost after commit; look up the original key")
        return receipt
