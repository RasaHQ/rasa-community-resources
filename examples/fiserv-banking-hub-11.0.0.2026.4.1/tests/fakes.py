"""An authored, vendor-free stand-in for the release client, so host tests run in CI.

It returns the same domain results as the mock without any vendor definition. It
is a test double, not a contract mock: contract behaviour is tested separately
when the learner-supplied file is present.
"""
from bh_demo.client import Unavailable

PARTIES = {"PARTY-A": [("5550010001", "DDA"), ("5550010002", "SDA"), ("5550019001", "LOAN")],
           "PARTY-B": [("5550020001", "DDA"), ("5550020002", "SDA"), ("5550029001", "LOAN")]}
DATES = {"5550019001": "2026-12-01", "5550029001": "2026-12-10"}


class FakeClient:
    def __init__(self):
        self.calls = []

    def party_accounts(self, party):
        self.calls.append(("party", party))
        if party not in PARTIES:
            raise Unavailable("not_success")
        return list(PARTIES[party])

    def next_payment_date(self, ident):
        self.calls.append(("acct", ident))
        if ident not in DATES:
            raise Unavailable("no_matching_account")
        return DATES[ident]
