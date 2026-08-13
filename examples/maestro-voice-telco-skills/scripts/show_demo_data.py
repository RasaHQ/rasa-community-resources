#!/usr/bin/env python3
"""Print the demo customer's telecom data — the presenter's cheat sheet.

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

from lib.database import DEMO_CUSTOMER_ID, DEMO_USERNAME, Database, get_customer_by_name

_TTY = sys.stdout.isatty()
GREEN = "\033[92m" if _TTY else ""
BLUE = "\033[94m" if _TTY else ""
MAGENTA = "\033[95m" if _TTY else ""
BOLD = "\033[1m" if _TTY else ""
DIM = "\033[2m" if _TTY else ""
RESET = "\033[0m" if _TTY else ""


def main() -> None:
    db = Database()
    customer = get_customer_by_name(db, DEMO_USERNAME)
    if customer is None:
        print(f"Demo customer '{DEMO_USERNAME}' not found. Run: make reset-db")
        sys.exit(1)

    customer_id, first_name, last_name, name, email, address, plan_name = customer
    print(
        f"\n{BOLD}{MAGENTA}Demo customer: {name}{RESET}"
        f"  {DIM}(id {customer_id}, {plan_name}){RESET}\n"
    )
    print(f"{BLUE}{BOLD}Profile{RESET}")
    print(f"  {GREEN}email{RESET}    {email}")
    print(f"  {GREEN}address{RESET}  {address}")
    print(f"  {GREEN}plan{RESET}     {plan_name}")

    print(f"\n{BLUE}{BOLD}Bills{RESET}")
    bills = db.run_query(
        "SELECT date, amount, source FROM billing WHERE customer_id = ? ORDER BY date",
        (str(customer_id),),
        one_record=False,
    )
    for date, amount, source in bills or []:
        print(f"  {GREEN}{date}{RESET}  ${float(amount):,.2f}  {source}")

    print(f"\n{BLUE}{BOLD}Routers{RESET}")
    routers = db.run_query(
        "SELECT device_id, model, status, wifi_name FROM routers WHERE customer_id = ?",
        (str(customer_id),),
        one_record=False,
    )
    for device_id, model, status, wifi_name in routers or []:
        print(
            f"  {GREEN}{device_id}{RESET}  {model:<22} {status:<10} "
            f"{DIM}{wifi_name or '-'}{RESET}"
        )

    print(f"\n{BLUE}{BOLD}Try saying{RESET}")
    print('  "My internet is slow"')
    print('  "Can you explain my February bill?"')
    if routers:
        print(f'  "Please factory-reset my router {routers[0][0]}"')
    print(f"\n{DIM}Default customer_id for tools: {DEMO_CUSTOMER_ID}{RESET}\n")


if __name__ == "__main__":
    main()
