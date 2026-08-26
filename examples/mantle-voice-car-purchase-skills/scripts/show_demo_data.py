#!/usr/bin/env python3
"""Print the demo customer's data — the presenter's cheat sheet.

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

from lib.cars import load_cars
from lib.database import DEMO_USERNAME, Database, get_user_id

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
    print(f"\n{BOLD}{MAGENTA}🚗 Demo customer: {DEMO_USERNAME}{RESET}"
          f"  {DIM}({segment[0] if segment else 'unknown'} segment){RESET}\n")

    print(f"{BLUE}{BOLD}Accounts{RESET}")
    accounts = db.run_query(
        "SELECT number, type, balance FROM accounts WHERE user_id = ? ORDER BY type",
        (user_id,),
        one_record=False,
    )
    for number, acc_type, balance in accounts or []:
        print(f"  {GREEN}{number}{RESET}  {acc_type:<9} ${balance:,.2f}")

    print(f"\n{BLUE}{BOLD}Existing loans{RESET}")
    loans = db.run_query(
        """
        SELECT lender, purpose, monthly_payment, remaining_months
        FROM loans WHERE user_id = ?
        """,
        (user_id,),
        one_record=False,
    )
    for lender, purpose, monthly_payment, remaining_months in loans or []:
        print(
            f"  {GREEN}{lender:<22}{RESET} {purpose:<14} "
            f"${monthly_payment:,.2f}/mo  {DIM}{remaining_months} months left{RESET}"
        )
    if not loans:
        print(f"  {DIM}none{RESET}")

    cars = load_cars()
    dealers = sorted({car["dealer_location"] for car in cars})
    print(f"\n{BLUE}{BOLD}Inventory{RESET}  {DIM}({len(cars)} cars, {len(dealers)} dealers){RESET}")
    for car in cars[:5]:
        print(
            f"  {GREEN}{car['model']:<28}{RESET} {car['type']:<13} "
            f"${car['price']:>9,.0f}  {DIM}{car['dealer_location']}{RESET}"
        )
    print(f"  {DIM}...and {max(len(cars) - 5, 0)} more{RESET}")

    print(f"\n{BLUE}{BOLD}Dealers{RESET}")
    for dealer in dealers:
        count = sum(1 for car in cars if car["dealer_location"] == dealer)
        print(f"  {GREEN}{dealer:<22}{RESET} {DIM}{count} cars{RESET}")

    print(f"\n{BLUE}{BOLD}Try saying{RESET}")
    if accounts:
        print(f'  "What is the balance on account {accounts[0][0]}?"')
    if cars:
        first = cars[0]
        print(f"  \"Do you have a {first['model']} in stock?\"")
        print(f"  \"Reserve the {first['model']} at {first['dealer_location']}\"")
    print('  "I want a compact SUV under thirty thousand"')
    print('  "Book me a test drive next week"')
    print('  "What would the monthly payment be over sixty months?"')
    print('  "Can you check my credit score?"')
    print()


if __name__ == "__main__":
    main()
