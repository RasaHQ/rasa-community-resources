import sqlite3
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from seat_allocation import initialize, reserve, inventory, stale_read_demo, connect


class Seats(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)/'seats.db'; initialize(self.path)

    def test_nonnegative_counter_can_hide_overbooking(self):
        self.assertEqual(stale_read_demo(self.path), [1, 1])
        stored = inventory(self.path)
        self.assertEqual(stored['flights'][0], ('F1', 0))
        self.assertEqual(len(stored['reservations']), 2)

    def test_competing_connections_allocate_one_seat(self):
        with ThreadPoolExecutor(max_workers=8) as pool:
            result = list(pool.map(lambda i: reserve(self.path, str(i), 'F1'), range(8)))
        self.assertEqual(result.count('reserved'), 1)
        self.assertEqual(result.count('unavailable'), 7)
        self.assertEqual(len(inventory(self.path)['reservations']), 1)

    def test_lost_response_retry_returns_saved_reservation(self):
        reserve(self.path, 'a', 'F1')
        self.assertEqual(reserve(self.path, 'a', 'F1'), 'reserved_replay')
        self.assertEqual(inventory(self.path)['flights'][0], ('F1', 0))

    def test_same_identity_concurrent_retries_spend_once(self):
        with ThreadPoolExecutor(max_workers=4) as pool:
            result = list(pool.map(lambda _: reserve(self.path, 'a', 'F1'), range(4)))
        self.assertEqual(result.count('reserved'), 1)
        self.assertEqual(result.count('reserved_replay'), 3)

    def test_identity_collision_does_not_spend_second_flight(self):
        reserve(self.path, 'a', 'F1')
        with self.assertRaises(ValueError): reserve(self.path, 'a', 'F2')
        self.assertEqual(inventory(self.path)['flights'][1], ('F2', 1))

    def test_insert_failure_rolls_back_seat_decrement(self):
        db = connect(self.path)
        db.execute("CREATE TRIGGER fail_insert BEFORE INSERT ON reservations BEGIN SELECT RAISE(ABORT, 'fixture failure'); END")
        db.close()
        with self.assertRaises(sqlite3.IntegrityError): reserve(self.path, 'a', 'F1')
        self.assertEqual(inventory(self.path)['flights'][0], ('F1', 1))
        self.assertEqual(inventory(self.path)['reservations'], [])

    def test_unknown_flight_is_unavailable(self):
        self.assertEqual(reserve(self.path, 'a', 'missing'), 'unavailable')
        self.assertEqual(inventory(self.path)['reservations'], [])

    def test_invalid_identity_is_rejected(self):
        with self.assertRaises(ValueError): reserve(self.path, '', 'F1')


if __name__ == '__main__': unittest.main()
