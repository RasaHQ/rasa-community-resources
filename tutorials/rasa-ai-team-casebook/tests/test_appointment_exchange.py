"""Exercise durable service states, not a model conversation or HTTP service."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

SOURCE = Path(__file__).resolve().parents[1] / "appointment_exchange.py"
spec = importlib.util.spec_from_file_location("appointment_exchange", SOURCE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
Scheduler, LostReply = module.Scheduler, module.LostReply


class AppointmentExchange(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.path = Path(self.folder.name) / "schedule.sqlite"
        self.service = Scheduler(self.path)
        self.addCleanup(lambda: self.service.close())
        self.service.seed()
        self.service.hold("hold-1", "customer-1", "Wednesday 11:00", "fibre", 120, 100)

    def exchange(self, **changes):
        args = dict(request_key="request-1", old_id="visit-1", revision=1,
                    hold_id="hold-1", customer="customer-1",
                    confirmed_capability="fibre", now=110)
        return self.service.exchange(**{**args, **changes})

    def old_still_active(self):
        self.assertEqual([row["id"] for row in self.service.active()], ["visit-1"])

    def test_expiry_preserves_the_original_booking(self):
        self.assertEqual(self.exchange(now=120)["reason"], "hold_expired")
        self.old_still_active()

    def test_changed_booking_is_not_overwritten(self):
        self.service.db.execute("UPDATE bookings SET revision=2 WHERE id='visit-1'")
        self.service.db.commit()
        self.assertEqual(self.exchange()["reason"], "booking_changed")
        self.old_still_active()

    def test_changed_requirement_needs_a_new_offer(self):
        self.assertEqual(self.exchange(confirmed_capability="copper")["reason"],
                         "requirements_changed")
        self.old_still_active()

    def test_other_customer_cannot_consume_the_hold(self):
        self.assertEqual(self.exchange(customer="customer-2")["status"], "refused")
        self.old_still_active()

    def test_failure_between_writes_rolls_back(self):
        with self.assertRaises(RuntimeError):
            self.exchange(fail_at="after_old_release")
        self.old_still_active()
        self.assertEqual(self.service.lookup("request-1"), {"status": "unknown"})
        self.assertEqual(self.exchange()["status"], "succeeded")

    def test_lost_reply_resolves_after_reopening_database(self):
        with self.assertRaises(LostReply):
            self.exchange(fail_at="after_commit")
        self.service.close()
        self.service = Scheduler(self.path)
        receipt = self.service.lookup("request-1")
        self.assertEqual(receipt["slot"], "Wednesday 11:00")
        self.assertEqual([row["id"] for row in self.service.active()], [receipt["newBooking"]])
        self.assertTrue(self.exchange(now=150)["replayed"])
        self.assertEqual(len(self.service.active()), 1)

    def test_same_key_cannot_confirm_a_different_choice(self):
        self.exchange()
        self.assertEqual(self.exchange(confirmed_capability="copper")["reason"],
                         "request_changed")
        self.assertEqual(len(self.service.active()), 1)

    def test_another_customer_cannot_hold_the_reserved_slot(self):
        with self.assertRaisesRegex(ValueError, "slot unavailable"):
            self.service.hold("hold-2", "customer-2", "Wednesday 11:00", "fibre", 130, 110)


if __name__ == "__main__":
    unittest.main()
