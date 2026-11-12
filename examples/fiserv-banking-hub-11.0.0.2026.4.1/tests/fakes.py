"""An authored, vendor-free stand-in for the release client, so host tests run in CI.

It returns the same domain results as the mock without any vendor definition. It
is a test double, not a contract mock: contract behaviour is tested separately
when the learner-supplied file is present.
"""
from decimal import Decimal

from bh_demo.client import Unavailable, UnknownOutcome

PARTIES = {"PARTY-A": [("5550010001", "DDA"), ("5550010002", "SDA"), ("5550019001", "LOAN")],
           "PARTY-B": [("5550020001", "DDA"), ("5550020002", "SDA"), ("5550029001", "LOAN")]}
KINDS = {ident: kind for rows in PARTIES.values() for ident, kind in rows}
BALANCES = {"5550010001": Decimal("1250.00"), "5550010002": Decimal("5400.00"),
            "5550020001": Decimal("800.00"), "5550020002": Decimal("50.00")}
PAYMENTS = {"5550019001": {"due_date": "2026-12-01", "amount": "182.40", "currency": "USD"},
            "5550029001": {"due_date": "2026-12-10", "amount": "91.00", "currency": "USD"}}


class FakeMock:
    def __init__(self):
        self.transfers = 0


class FakeClient:
    def __init__(self, fault="none"):
        self.mock, self.fault, self.balances = FakeMock(), fault, dict(BALANCES)
        self.calls = []

    def party_accounts(self, party):
        self.calls.append(("party", party))
        if party not in PARTIES:
            raise Unavailable("not_success")
        return list(PARTIES[party])

    def available_balance(self, ident):
        self.calls.append(("acct", ident))
        if KINDS.get(ident) != "DDA":
            raise Unavailable("no_matching_account")
        return self.balances[ident]

    def loan_payment(self, ident):
        self.calls.append(("acct", ident))
        if ident not in PAYMENTS:
            raise Unavailable("no_matching_account")
        return dict(PAYMENTS[ident])

    def transfer(self, source, source_type, destination, destination_type, amount):
        self.calls.append(("xfer", source, destination))
        if (KINDS.get(source) != source_type or KINDS.get(destination) != destination_type
                or source_type != "DDA" or destination_type not in {"DDA", "SDA"}
                or amount > self.balances[source]):
            return "refused"
        self.balances[source] -= amount
        self.balances[destination] += amount
        self.mock.transfers += 1
        if self.fault == "transfer-response-lost":
            raise UnknownOutcome("no_reply")
        return "accepted"


class FakeFixture:
    def __init__(self, contract=None, fault="none"):
        self.client = FakeClient(fault)
        self.mock = self.client.mock

    def close(self):
        pass
