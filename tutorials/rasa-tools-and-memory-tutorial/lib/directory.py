"""In-memory demo data.

Deliberately not a database: the tutorial is about tool and memory scope, and a
dict keeps every example runnable with no setup beyond two API keys.
"""

from __future__ import annotations

CUSTOMERS: dict[str, dict] = {
    "MB-4417": {
        "customer_id": "MB-4417",
        "name": "Dana Okafor",
        "segment": "Retail",
        "passphrase": "bluebird",
        "accounts": {
            "10029384": {"type": "current", "balance": 2418.55},
            "10029385": {"type": "savings", "balance": 9120.00},
        },
        "payees": {"Sam Rivera": "20447781"},
    }
}

# The demo authenticates on passphrase alone. A real deployment would call an
# identity provider here; the shape of the tool would not change.
PASSPHRASES = {c["passphrase"]: cid for cid, c in CUSTOMERS.items()}


def customer_by_passphrase(passphrase: str) -> dict | None:
    cid = PASSPHRASES.get(passphrase.strip().lower())
    return CUSTOMERS.get(cid) if cid else None


def customer_by_id(customer_id: str) -> dict | None:
    return CUSTOMERS.get(customer_id)
