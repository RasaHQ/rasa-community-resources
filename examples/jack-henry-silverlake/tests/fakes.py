"""Vendor-free test doubles so the host, guard, journal and fault rules run in CI.

They are test doubles, not a contract mock: schema behaviour is tested separately
when the learner-supplied archive is present.
"""
from decimal import Decimal

from silverlake_demo.client import Unavailable, UnknownOutcome

CUSTOMERS = {"C100001": [("1001001", "D"), ("1001002", "S"), ("7001001", "L")],
             "C200002": [("2001001", "D"), ("2001002", "S"), ("8001001", "L")]}


class FakeMock:
    def __init__(self):
        self.transfers = 0


class FakeClient:
    def __init__(self, fault="none"):
        self.mock, self.fault = FakeMock(), fault
        self.balances = {"1001001": Decimal("1250.00"), "1001002": Decimal("300.00"),
                         "2001001": Decimal("800.00"), "2001002": Decimal("50.00")}

    def accounts(self, customer):
        if customer not in CUSTOMERS:
            raise Unavailable("fault")
        return list(CUSTOMERS[customer])

    def available_balance(self, ident, kind):
        if ident not in self.balances:
            raise Unavailable("fault")
        return format(self.balances[ident], "f")

    def history(self, ident, kind, cursor=None, max_rec=3):
        return [{"date": "2026-11-04", "amount": "42.00", "direction": "debit", "currency": "USD"}], None

    def loan_payment(self, ident):
        return {"amount_due": "242.40", "next_due_date": "2026-12-01", "currency": "USD"}

    def payoff(self, ident, date):
        if date != "2026-11-20":
            raise Unavailable("no_quote_for_date")
        return {"as_of": date, "amount": "4120.55", "currency": "USD"}

    def transfer(self, source, destination, amount):
        if source[0] not in self.balances or destination[0] not in self.balances or amount > self.balances[source[0]]:
            return "refused"
        self.balances[source[0]] -= amount
        self.balances[destination[0]] += amount
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
