#!/usr/bin/env python3
"""Print the demo customer's banking data — the presenter's cheat sheet.

Usage:
    make show-demo-data
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
os.chdir(PROJECT_ROOT)
sys.path.insert(0, str(PROJECT_ROOT))

from lib.database import DEMO_USERNAME, Database, get_user_id, mask_card

_TTY = sys.stdout.isatty()
GREEN = "\033[92m" if _TTY else ""
BLUE = "\033[94m" if _TTY else ""
MAGENTA = "\033[95m" if _TTY else ""
BOLD = "\033[1m" if _TTY else ""
DIM = "\033[2m" if _TTY else ""
RESET = "\033[0m" if _TTY else ""


def main() -> None:
    db = Database()
    user_id = get_user_id(db, DEMO_USERNAME)
    if user_id is None:
        print(f"Demo customer '{DEMO_USERNAME}' not found. Run: make reset-db")
        sys.exit(1)

    segment = db.run_query("SELECT segment FROM users WHERE id = ?", (user_id,))
    print(f"\n{BOLD}{MAGENTA}🏦 Demo customer: {DEMO_USERNAME}{RESET}"
          f"  {DIM}({segment[0] if segment else 'unknown'} segment){RESET}\n")

    print(f"{BLUE}{BOLD}Accounts{RESET}")
    accounts = db.run_query(
        "SELECT number, type, balance FROM accounts WHERE user_id = ? ORDER BY type",
        (user_id,),
        one_record=False,
    )
    for number, acc_type, balance in accounts or []:
        print(f"  {GREEN}{number}{RESET}  {acc_type:<9} ${balance:,.2f}")

    print(f"\n{BLUE}{BOLD}Cards{RESET}")
    cards = db.run_query(
        "SELECT number, type, status FROM cards WHERE user_id = ?",
        (user_id,),
        one_record=False,
    )
    for number, card_type, status in cards or []:
        print(f"  {GREEN}{mask_card(number)}{RESET}  {card_type:<7} {status}")

    print(f"\n{BLUE}{BOLD}Payees{RESET}")
    payees = db.run_query(
        "SELECT name, account_number, type, reference FROM payees WHERE user_id = ?",
        (user_id,),
        one_record=False,
    )
    for name, account_number, payee_type, reference in payees or []:
        print(f"  {GREEN}{name:<14}{RESET} {account_number}  {payee_type:<9} {DIM}{reference}{RESET}")

    print(f"\n{BLUE}{BOLD}Try saying{RESET}")
    if accounts:
        print(f'  "What is the balance on account {accounts[0][0]}?"')
    if payees:
        print(f'  "Send 25 dollars to {payees[0][0]} from my current account"')
    if cards:
        print(f'  "My card ending in {cards[0][0][-4:]} was stolen"')
    print()


if __name__ == "__main__":
    main()
