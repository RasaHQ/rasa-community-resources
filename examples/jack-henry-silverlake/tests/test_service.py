from pathlib import Path
import tempfile
import unittest

from host import Refused
from journal import Journal
from silverlake_demo.permissions import PERMISSIONS
from silverlake_demo.service import SilverLakeService
from tests.support import Clock, load_contract
from tests.test_wire import Fixture


class ServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = load_contract()

    def build(self, fault="none"):
        self.fx = Fixture(self.contract, fault)
        self.addCleanup(self.fx.close)
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.journal_dir = Path(folder.name) / "journal"
        self.journal = Journal(self.journal_dir, "silverlake-mock", initialize=True)
        self.addCleanup(self.journal.close)
        self.clock = Clock()
        self.service = SilverLakeService(self.fx.client, self.journal, PERMISSIONS, clock=self.clock)
        return self.service.open_session("demo-A")

    def transfer(self, token, amount="25", turn=4, utterance="confirm transfer"):
        review = self.service.review_transfer(token, "checking-A", "savings-A", amount, "USD")
        self.service.arm(token, review["review"], turn)
        return self.service.confirm_and_send(token, utterance, turn + 1)

    def test_reads_are_scoped_to_permitted_aliases(self):
        token = self.build()
        self.assertEqual(self.service.accounts(token)["accounts"], ["checking-A", "loan-A", "savings-A"])
        self.assertEqual(self.service.balance(token, "savings-A")["amount"], "300.00")
        for call in (lambda: self.service.balance(token, "checking-B"),
                     lambda: self.service.balance(token, "loan-A")):
            with self.assertRaises(Refused):
                call()
        payment = self.service.loan_payment(token, "loan-A")
        self.assertEqual((payment["amount_due"], payment["next_due_date"]), ("242.40", "2026-12-01"))
        self.assertEqual(self.service.payoff(token, "loan-A", "2026-11-20")["amount"], "4120.55")
        self.assertEqual(self.service.payoff(token, "loan-A", "2026-12-24")["state"], "unavailable")

    def test_read_assurance_expires_at_300_seconds(self):
        token = self.build()
        self.clock.now += 299
        self.service.balance(token, "checking-A")
        self.clock.now += 1
        with self.assertRaises(Refused):
            self.service.balance(token, "checking-A")
        self.service.assure(token)
        self.service.balance(token, "checking-A")

    def test_one_confirmed_review_sends_once(self):
        token = self.build()
        self.assertEqual(self.transfer(token)["state"], "accepted")
        with self.assertRaises(Refused):
            self.service.confirm_and_send(token, "confirm transfer", 5)  # consumed
        self.assertEqual(self.fx.mock.transfers, 1)
        self.assertEqual(self.service.status(token)["state"], "accepted")

    def test_wrong_turn_wrong_words_and_expiry_send_nothing(self):
        token = self.build()
        review = self.service.review_transfer(token, "checking-A", "savings-A", "5", "USD")
        self.service.arm(token, review["review"], 4)
        with self.assertRaises(Refused):
            self.service.confirm_and_send(token, "confirm transfer", 6)  # not the next turn
        with self.assertRaises(Refused):
            self.transfer(token, utterance="what is my balance")
        review = self.service.review_transfer(token, "checking-A", "savings-A", "5", "USD")
        self.service.arm(token, review["review"], 8)
        self.clock.now += 30
        with self.assertRaises(Refused):
            self.service.confirm_and_send(token, "confirm transfer", 9)  # review lifetime 30 s
        self.assertEqual(self.fx.mock.transfers, 0)

    def test_transfer_needs_assurance_younger_than_60_seconds(self):
        token = self.build()
        self.clock.now += 60
        review = self.service.review_transfer(token, "checking-A", "savings-A", "5", "USD")
        with self.assertRaises(Refused):
            self.service.arm(token, review["review"], 4)
        self.assertEqual(self.fx.mock.transfers, 0)

    def test_unknown_outcome_holds_the_principal_across_sessions_and_restart(self):
        token = self.build(fault="transfer-response-lost")
        self.assertEqual(self.transfer(token)["state"], "unknown")
        again = self.service.open_session("demo-A")
        with self.assertRaises(Refused):
            self.service.review_transfer(again, "checking-A", "savings-A", "1", "USD")
        self.assertEqual(self.service.status(again)["state"], "unknown")
        self.assertEqual(self.service.balance(again, "checking-A")["state"], "supplied")
        self.journal.close()
        reopened = Journal(self.journal_dir, "silverlake-mock")
        self.addCleanup(reopened.close)
        self.assertTrue(reopened.held("demo-A"))
        self.assertFalse(reopened.held("demo-B"))
        self.assertEqual(self.fx.mock.transfers, 1)


if __name__ == "__main__":
    unittest.main()
