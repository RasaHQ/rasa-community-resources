"""Our fictional banking contract, never a representation of vendor wire fields."""

from decimal import Decimal
from importlib.resources import files
import json


class Unsupported(Exception):
    """No supplied capability or quote; never fabricate a financial value."""


class BankingMock:
    """Two illustrative configurations of one shared, deterministic domain mock."""

    def __init__(self, profile, *, fault="none"):
        if profile not in {"jack-henry", "fiserv"}:
            raise ValueError("unknown illustrative profile")
        if fault not in {"none", "transfer-response-lost"}:
            raise ValueError("unknown domain fault")
        self.profile = profile
        self.config = json.loads(files("banking_demo").joinpath("profiles", profile + ".json").read_text())
        self.fault = fault
        self.operations = {}

    @staticmethod
    def allows_transfer(source, destination):
        deposits = {f"{kind}-{owner}" for kind in ("checking", "savings") for owner in ("A", "B")}
        return source in deposits and destination in deposits and source[-1] == destination[-1]

    def balance(self, account, balance_type="available"):
        if not account.startswith(("checking-", "savings-")):
            raise Unsupported()
        return {"amount": self.config["balances"][balance_type], "currency": "USD"}

    def history(self, account, page):
        if not account.startswith(("checking-", "savings-")):
            raise Unsupported()
        rows = [
            {"date": "2026-01-14", "amount": "-5.00", "currency": "USD", "state": "posted"},
            {"date": "2026-01-13", "amount": "20.00", "currency": "USD", "state": "posted"},
        ]
        return {"entries": rows[page - 1:page], "page": page, "more": page < len(rows)}

    def loan_payment(self, account):
        if not account.startswith("loan-"):
            raise Unsupported()
        return {"due_date": "2026-01-20", "amount": "75.00", "currency": "USD"}

    def payoff(self, account, date):
        if not account.startswith("loan-") or date != "2026-01-15":
            raise Unsupported()
        # A supplied fictional quote on one date, not an invented calculation.
        return {"as_of": date, "amount": self.config["payoff"], "currency": "USD"}

    def submit(self, operation, transfer):
        if operation in self.operations:
            return self.operations[operation]
        if (not self.allows_transfer(transfer.source, transfer.destination)
                or Decimal(transfer.amount) > Decimal(self.config["balances"]["available"])):
            state = "refused"
        else:
            state = self.config["transfer_outcome"]
        self.operations[operation] = state
        if self.fault == "transfer-response-lost":
            raise TimeoutError("fictional response loss")
        return state
