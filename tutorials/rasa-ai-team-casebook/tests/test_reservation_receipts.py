import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from reservation_receipts import reserve, cancel, initialize, inventory, read_current, answer_allocation


class ReservationReceipts(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'reservations.db'
        initialize(self.path)

    def first(self):
        return reserve(self.path, 'request-A', 'passenger-A')

    def test_historical_receipt_replays_correctly_after_cancellation(self):
        original = self.first()
        cancel(self.path, original['reservation'])
        self.assertEqual(self.first(), original)
        self.assertEqual(read_current(self.path, original['reservation'])['state'], 'cancelled')

    def test_reallocation_preserves_capacity_but_old_receipt_does_not_answer_current_state(self):
        original = self.first()
        cancel(self.path, original['reservation'])
        reserve(self.path, 'request-B', 'passenger-B')
        before = inventory(self.path)
        audit = []
        replay = reserve(self.path, 'request-A', 'passenger-A', audit=audit)
        self.assertEqual(audit, [{'kind': 'operation_replay', 'changed_rows': 0}])
        self.assertEqual(replay, original)
        self.assertEqual(inventory(self.path), before)
        self.assertEqual(before['remaining'], 0)
        self.assertEqual([row['passenger'] for row in before['active']], ['passenger-B'])
        self.assertTrue(replay['outcome'] == 'reserved')
        answer = answer_allocation(replay, read_current(self.path, replay['reservation']))
        self.assertFalse(answer['is_allocated'])
        self.assertEqual(answer['operation_outcome'], 'reserved')
        self.assertEqual(answer['observed_version'], 2)

    def test_active_observation_answers_true(self):
        receipt = self.first()
        self.assertTrue(answer_allocation(receipt, read_current(self.path, receipt['reservation']))['is_allocated'])

    def test_missing_observation_is_unknown_not_a_cancellation(self):
        self.assertIsNone(answer_allocation(self.first(), None)['is_allocated'])

    def test_other_reservation_cannot_supply_status(self):
        original = self.first()
        cancel(self.path, original['reservation'])
        replacement = reserve(self.path, 'request-B', 'passenger-B')
        with self.assertRaises(ValueError):
            answer_allocation(original, read_current(self.path, replacement['reservation']))

    def test_replaying_cancel_after_reallocation_does_not_release_seat_twice(self):
        original = self.first()
        cancel(self.path, original['reservation'])
        reserve(self.path, 'request-B', 'passenger-B')
        cancel(self.path, original['reservation'])
        self.assertEqual(inventory(self.path)['remaining'], 0)
        self.assertEqual(len(inventory(self.path)['active']), 1)

    def test_concurrent_cancel_releases_exactly_once(self):
        original = self.first()
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(lambda _: cancel(self.path, original['reservation']), range(4)))
        self.assertEqual(inventory(self.path)['remaining'], 1)
        self.assertEqual(inventory(self.path)['active'], [])

    def test_cancelled_create_identity_does_not_reactivate_when_capacity_is_free(self):
        original = self.first()
        cancel(self.path, original['reservation'])
        self.first()
        self.assertEqual(inventory(self.path)['remaining'], 1)
        self.assertEqual(inventory(self.path)['active'], [])

    def test_reused_request_with_different_passenger_is_rejected(self):
        self.first()
        with self.assertRaises(ValueError): reserve(self.path, 'request-A', 'passenger-B')
        self.assertEqual(len(inventory(self.path)['operations']), 1)

    def test_unknown_cancellation_preserves_capacity(self):
        with self.assertRaises(ValueError): cancel(self.path, 'unknown')
        self.assertEqual(inventory(self.path)['remaining'], 1)


if __name__ == '__main__': unittest.main()
