#!/usr/bin/env python3
"""Print the seeded demo bank so you know what to ask for before you call."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib.bank import ACCOUNTS, CARDS, CUSTOMER, TRANSACTIONS  # noqa: E402


def main() -> int:
    print(f"\nCustomer: {CUSTOMER['name']}  ({CUSTOMER['customer_id']})\n")

    print("Accounts")
    for key, acc in ACCOUNTS.items():
        print(f"  {key:<10} {acc['label']:<20} ${acc['balance']:>10,.2f}  ends {acc['last_four']}")

    print("\nCards")
    for last_four, card in CARDS.items():
        print(f"  ends {last_four}  {card['type']:<7} {card['status']}")

    print("\nRecent transactions")
    for txn in sorted(TRANSACTIONS, key=lambda t: t["date"], reverse=True):
        print(f"  {txn['date']}  {txn['merchant']:<18} ${txn['amount']:>8,.2f}")

    # Digits, not words: typed into the Inspector "four five three two" would
    # normalise to nothing. Spoken, ASR returns numerals and either works.
    print("\nTry: \"what's my checking balance\", \"move fifty dollars to savings\",")
    print("     \"I lost my card, it ends 4532\", \"recent transactions\"\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
