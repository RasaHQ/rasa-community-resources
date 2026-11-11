"""Missing host context refuses writes; not a channel-authentication test."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'examples/banking-shared'))
from banking_demo import BankingService, Refused, SessionContext


class CountingAdapter:
    def __init__(self):
        self.submissions = 0

    def submit(self, operation, transfer):
        self.submissions += 1
        return 'queued'


class MissingHostBoundary(unittest.TestCase):
    def test_model_fields_cannot_replace_missing_host_context_even_after_review(self):
        adapter = CountingAdapter()
        bank = BankingService(adapter, clock=lambda: 100)
        host = SessionContext('private-host-fixture', 1, 'fictional-caller',
                              frozenset({'checking-A', 'savings-A'}), 1000)
        bank.open_session(host)
        review = bank.review_transfer(host, 'checking-A', 'savings-A', '10.00', 'USD')
        bank.confirm(host, review['review'],
                     {key: review[key] for key in ('source', 'destination', 'amount', 'currency')})
        # A real host registered/confirmed this fixture. Missing transport proof
        # and a model's plausible authority fields still cannot submit it.
        for untrusted in (None, {}, {'session': host.session, 'principal': host.principal,
                                     'confirmed': True, 'verified': True}):
            with self.subTest(untrusted=untrusted), self.assertRaises(Refused):
                bank.submit(untrusted, review['review'])
        self.assertEqual(adapter.submissions, 0)


if __name__ == '__main__':
    unittest.main()
