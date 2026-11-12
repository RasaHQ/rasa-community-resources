"""An authored, vendor-free stand-in for the Premier client, so host tests run in CI.

It returns the same domain results as the mock without any vendor definition.
It is a test double, not a contract mock: contract behaviour is tested separately
when the learner-supplied file is present.
"""
from decimal import Decimal

from premier_demo.client import Unavailable, UnknownOutcome

PARTIES = {"PARTY-A": [("5550010001", "DDA"), ("5550010002", "DDA"), ("5550019001", "LOAN")],
           "PARTY-B": [("5550020001", "DDA"), ("5550020002", "DDA"), ("5550029001", "LOAN")]}
BALANCES = {"5550010001": Decimal("1250.00"), "5550010002": Decimal("300.00"),
            "5550020001": Decimal("800.00"), "5550020002": Decimal("50.00")}


class FakeMock:
    def __init__(self):
        self.transfers = 0


class FakeClient:
    def __init__(self, fault="none"):
        self.mock, self.fault, self.balances = FakeMock(), fault, dict(BALANCES)

    def party_accounts(self, party):
        if party not in PARTIES:
            raise Unavailable("status_404")
        return list(PARTIES[party])

    def available_balance(self, ident):
        if ident not in self.balances:
            raise Unavailable("status_404")
        return self.balances[ident]

    def transactions(self, ident, cursor=None):
        rows = [{"date": "2026-11-04", "direction": "debit", "amount": "42.00", "currency": "USD"}]
        return (rows, None) if ident in self.balances else (_ for _ in ()).throw(Unavailable("status_404"))

    def loan_payment(self, ident):
        return {"due_date": "2026-12-01", "amount": "182.40", "currency": "USD"}

    def current_payoff(self, ident):
        return {"amount": "4120.55", "currency": "USD"}

    def transfer(self, source, destination, amount):
        if source not in self.balances or destination not in self.balances or amount > self.balances[source]:
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
