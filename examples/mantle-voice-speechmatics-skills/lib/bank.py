"""In-memory demo bank, and the two voice-specific normalisers it needs.

Seeded from the original Rime voice demo so the numbers a listener hears are
the ones that demo was tuned around. There is no database to set up: the point
of this resource is the voice stack, not persistence.

The normalisers are the part worth copying. Both exist because *speech* reaches
a tool differently from typing, and both were learned the hard way in the demo
this resource comes from.
"""

from __future__ import annotations

CUSTOMER = {
    "customer_id": "cust_0417",
    "name": "Alex Chen",
}

ACCOUNTS = {
    "checking": {"label": "Everyday Checking", "balance": 2450.75, "last_four": "4532"},
    "savings": {"label": "Rainy Day Savings", "balance": 15230.00, "last_four": "7390"},
}

TRANSACTIONS = [
    {"date": "2026-12-01", "merchant": "Grocery Store", "amount": -75.00},
    {"date": "2026-12-02", "merchant": "Gas Station", "amount": -40.00},
    {"date": "2026-12-03", "merchant": "Restaurant", "amount": -60.00},
]

CARDS = {"4532": {"type": "debit", "status": "active"}}


def normalise_account_type(spoken: str | None) -> str | None:
    """Map what a caller actually says onto an account key.

    An ASR transcript is not a menu choice. "check", "checking", "my current
    one", "chequing" all mean the same account, and a dictionary lookup on the
    raw string misses every one of them but the exact match.
    """
    if not spoken:
        return None
    text = spoken.strip().lower()
    if "sav" in text:
        return "savings"
    if "check" in text or "cheq" in text or "current" in text:
        return "checking"
    return None


def normalise_digits(spoken: str | None) -> str:
    """Strip everything that is not a digit from a spoken number.

    Voice transcription returns "4 5 3 2" or "4532" — the spacing is not stable
    and is not meaningful. Stripping to digits before comparing is what makes
    card matching work at all; without it the demo this came from rejected
    perfectly good input routinely.

    Known limit: this drops *words*, so "four five three two" collapses to "".
    Deepgram returns numerals for spoken digit strings, which is why that is
    survivable here — but an ASR configured to spell numbers out would need a
    word-to-digit pass in front of this. The skill asks the caller to repeat
    rather than guessing, which is the safe failure for a card block.
    """
    return "".join(c for c in str(spoken or "") if c.isdigit())


def get_account(spoken_type: str | None) -> tuple[str, dict] | tuple[None, None]:
    """Resolve a spoken account name to (key, record), or (None, None)."""
    key = normalise_account_type(spoken_type)
    if key is None:
        return None, None
    return key, ACCOUNTS[key]
