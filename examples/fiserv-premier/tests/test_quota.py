import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from premier_demo.host import Journal
from premier_demo import quota
from premier_demo.quota import Ledger, QuotaRefused

KEY = ("trial-1", "2026-11", "999990301", "runner-1")


class Wall:
    def __init__(self):
        self.now = 1_000_000.0

    def __call__(self):
        return self.now


def attestation(wall, **changes):
    record = {"budget_id": "B1", "trial_id": "trial-1", "period_id": "2026-11",
              "organization_id": "999990301", "runner_id": "runner-1", "operator": "operator",
              "as_of": wall.now, "expires_at": wall.now + 300, "remaining_core_attempts": 5,
              "basis": "operator reservation for this runner and window"}
    record.update(changes)
    return json.dumps(record).encode()


class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.path = Path(self.folder.name) / "quota.sqlite3"
        self.wall = Wall()
        self.ledger = Ledger(self.path, clock=self.wall)
        self.addCleanup(self._close)

    def _close(self):
        try:
            self.ledger.close()
        except Exception:
            pass

    def load(self, **changes):
        return self.ledger.import_budget(attestation(self.wall, **changes), approved_runner="runner-1")

    def test_a_fresh_matching_attestation_is_imported(self):
        self.assertEqual(self.load(), {"remaining": 5, "held": 0, "blocked": False})

    def test_bad_records_are_refused_before_any_use(self):
        for changes in ({"remaining_core_attempts": True}, {"remaining_core_attempts": -1},
                        {"remaining_core_attempts": 1001}, {"remaining_core_attempts": 2.0},
                        {"organization_id": "other"}, {"runner_id": "copy-on-another-runner"},
                        {"as_of": self.wall.now + 1}, {"as_of": self.wall.now - 300},
                        {"expires_at": self.wall.now}, {"expires_at": self.wall.now + 301},
                        {"basis": ""}, {"operator": 5}):
            with self.assertRaises(QuotaRefused, msg=str(changes)):
                self.load(**changes)
        with self.assertRaises(QuotaRefused):
            self.ledger.import_budget(b"not json", approved_runner="runner-1")
        with self.assertRaises(QuotaRefused):
            self.ledger.import_budget(json.dumps({"budget_id": "x"}).encode(), approved_runner="runner-1")
        with self.assertRaises(QuotaRefused):
            self.ledger.reserve("run", KEY)  # nothing was imported

    def test_freshness_boundary_is_299_versus_300_seconds(self):
        self.load(as_of=self.wall.now - 299, expires_at=self.wall.now + 1, budget_id="Bn")
        with self.assertRaises(QuotaRefused):
            self.load(as_of=self.wall.now - 300, expires_at=self.wall.now + 1, budget_id="Bx")

    def test_replay_and_alteration_never_replenish(self):
        raw = attestation(self.wall)
        self.ledger.import_budget(raw, approved_runner="runner-1")
        with self.assertRaises(QuotaRefused) as same:
            self.ledger.import_budget(raw, approved_runner="runner-1")
        self.assertEqual(str(same.exception), "budget_replay")
        with self.assertRaises(QuotaRefused) as altered:
            self.load(remaining_core_attempts=900)
        self.assertEqual(str(altered.exception), "budget_altered")
        self.wall.now += 1
        with self.assertRaises(QuotaRefused) as older:
            self.load(budget_id="B0", as_of=self.wall.now - 10, expires_at=self.wall.now + 100)
        self.assertEqual(str(older.exception), "budget_older")

    def test_two_reservations_cannot_overdraw_one_remaining_attempt(self):
        self.load(remaining_core_attempts=1)
        first = self.ledger.reserve("a", KEY, 1)
        with self.assertRaises(QuotaRefused):
            self.ledger.reserve("b", KEY, 1)
        self.ledger.charge_core_attempt(first)
        with self.assertRaises(QuotaRefused):
            self.ledger.charge_core_attempt(first)  # each reservation is consumed once
        self.assertEqual(self.ledger.snapshot(KEY), {"remaining": 0, "held": 0, "blocked": False})

    def test_per_run_limit_and_spacing(self):
        self.load(remaining_core_attempts=10)
        reservation = self.ledger.reserve("run", KEY, 3)
        self.ledger.charge_core_attempt(reservation)
        self.wall.now += 6.999
        with self.assertRaises(QuotaRefused) as early:
            self.ledger.charge_core_attempt(reservation)
        self.assertEqual(str(early.exception), "spacing")
        self.wall.now += 0.001
        self.ledger.charge_core_attempt(reservation)
        self.wall.now += 7
        self.ledger.charge_core_attempt(reservation)
        self.wall.now += 7
        with self.assertRaises(QuotaRefused):
            self.ledger.charge_core_attempt(reservation)  # a fourth is never reserved
        with self.assertRaises(QuotaRefused):
            self.ledger.reserve("run", KEY, 4)

    def test_rolling_window_ninth_allowed_tenth_refused_then_expires(self):
        # With 7 s spacing the window can never fill, so test the window alone.
        with mock.patch.object(quota, "MIN_SPACING", 0.0):
            self.load(remaining_core_attempts=30)
            for index in range(9):
                self.ledger.charge_core_attempt(self.ledger.reserve(f"r{index}", KEY, 1))
            tenth = self.ledger.reserve("tenth", KEY, 1)
            with self.assertRaises(QuotaRefused) as raised:
                self.ledger.charge_core_attempt(tenth)
            self.assertEqual(str(raised.exception), "rolling_window_limit")
            self.wall.now += 60.001  # the earlier attempts leave the rolling window
            self.load(budget_id="B2", remaining_core_attempts=21)
            self.ledger.charge_core_attempt(tenth)

    def test_rollover_counterexample_allows_at_most_one_physical_attempt(self):
        self.load(remaining_core_attempts=1)
        held = self.ledger.reserve("run", KEY, 1)
        self.wall.now += 5
        result = self.load(budget_id="B2", remaining_core_attempts=1)
        self.assertEqual(result, {"remaining": 1, "held": 1, "blocked": False})
        with self.assertRaises(QuotaRefused):
            self.ledger.reserve("other", KEY, 1)  # free is 0
        self.ledger.charge_core_attempt(held)  # the single physical attempt
        with self.assertRaises(QuotaRefused):
            self.ledger.charge_core_attempt(held)
        self.assertEqual(self.ledger.snapshot(KEY)["remaining"], 0)

    def test_rollover_after_the_send_does_not_replenish(self):
        self.load(remaining_core_attempts=1)
        held = self.ledger.reserve("run", KEY, 1)
        self.ledger.charge_core_attempt(held)
        self.wall.now += 5
        result = self.load(budget_id="B2", remaining_core_attempts=1)  # attested before the send was seen
        self.assertEqual(result["remaining"], 0)
        with self.assertRaises(QuotaRefused):
            self.ledger.reserve("again", KEY, 1)

    def test_attempt_charged_after_the_new_observation_is_subtracted(self):
        self.load(remaining_core_attempts=2)
        held = self.ledger.reserve("run", KEY, 2)
        self.wall.now += 10
        self.ledger.charge_core_attempt(held)  # at t+10
        self.wall.now += 10
        # B2 observed at t+5 says 2 remain: one attempt happened after that point
        result = self.load(budget_id="B2", as_of=self.wall.now - 15, expires_at=self.wall.now + 100,
                           remaining_core_attempts=2)
        self.assertEqual(result["remaining"], 1)

    def test_a_successor_below_the_holds_blocks_everything(self):
        self.load(remaining_core_attempts=3)
        held = self.ledger.reserve("run", KEY, 3)
        self.wall.now += 5
        result = self.load(budget_id="B2", remaining_core_attempts=1)
        self.assertTrue(result["blocked"])
        with self.assertRaises(QuotaRefused):
            self.ledger.charge_core_attempt(held)
        with self.assertRaises(QuotaRefused):
            self.ledger.reserve("x", KEY, 1)

    def test_expiry_blocks_reservation_and_send(self):
        self.load(remaining_core_attempts=2)
        held = self.ledger.reserve("run", KEY, 1)
        self.wall.now += 300
        with self.assertRaises(QuotaRefused):
            self.ledger.charge_core_attempt(held)
        with self.assertRaises(QuotaRefused):
            self.ledger.reserve("run2", KEY, 1)

    def test_state_survives_a_restart_and_a_journal_reset_cannot_replenish_it(self):
        self.load(remaining_core_attempts=1)
        held = self.ledger.reserve("run", KEY, 1)
        self.ledger.close()  # crash between import and send
        self.ledger = Ledger(self.path, clock=self.wall)
        journal = Journal(Path(self.folder.name) / "journal.sqlite3")
        journal.reset_fixture("new fictional exercise")
        journal.close()
        self.ledger.charge_core_attempt(held)
        with self.assertRaises(QuotaRefused):
            self.ledger.reserve("again", KEY, 1)

    def test_clock_rollback_fails_closed(self):
        self.load(remaining_core_attempts=2)
        self.wall.now -= 10
        with self.assertRaises(QuotaRefused) as raised:
            self.ledger.reserve("run", KEY, 1)
        self.assertEqual(str(raised.exception), "clock_rollback")

    def test_one_owner_and_one_token_attempt_per_run(self):
        with self.assertRaises(QuotaRefused):
            Ledger(self.path, clock=self.wall)
        self.ledger.charge_token_attempt("run")
        with self.assertRaises(QuotaRefused):
            self.ledger.charge_token_attempt("run")
        self.ledger.charge_token_attempt("other-run")


if __name__ == "__main__":
    unittest.main()
