"""The application builds choices and rechecks the read at execution."""
from dataclasses import dataclass
from threading import RLock


@dataclass(frozen=True)
class Snapshot:
    owner: str
    revision: int
    accounts: tuple[tuple[str, str], ...]


class Accounts:
    def __init__(self):
        self.lock = RLock()
        self.revision = 1
        self.records = {
            "A-CURRENT": ("demo-a", "current account", True),
            "A-SAVINGS": ("demo-a", "savings account", True),
            "B-CURRENT": ("demo-b", "current account", True),
        }
        self.reads = []

    def snapshot(self, owner):
        with self.lock:
            rows = tuple((key, label) for key, (who, label, active) in self.records.items()
                         if who == owner and active)
            return Snapshot(owner, self.revision, rows)

    def retire(self, account):
        with self.lock:
            owner, label, _ = self.records[account]
            self.records[account] = (owner, label, False)
            self.revision += 1

    def read(self, snapshot, choice):
        with self.lock:
            if self.revision != snapshot.revision:
                return {"status": "stale_options"}
            if choice not in dict(snapshot.accounts):
                return {"status": "choice_not_offered"}
            owner, label, active = self.records[choice]
            if owner != snapshot.owner or not active:
                return {"status": "account_unavailable"}
            self.reads.append(choice)
            return {"status": "transactions", "account": choice, "label": label,
                    "transactions": [{"reference": "DEMO-101", "merchant": "Aster Reading",
                                      "currency": "GBP", "amount": "-42.18"}]}
