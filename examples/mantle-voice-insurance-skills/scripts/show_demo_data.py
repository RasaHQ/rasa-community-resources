#!/usr/bin/env python3
"""Print the demo customer's insurance data — the presenter's cheat sheet.

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

from lib.database import CLAIM_STATUS_LABELS, DEMO_CUSTOMER_ID, DEMO_FIRST_NAME, Database

_TTY = sys.stdout.isatty()
GREEN = "\033[92m" if _TTY else ""
BLUE = "\033[94m" if _TTY else ""
MAGENTA = "\033[95m" if _TTY else ""
BOLD = "\033[1m" if _TTY else ""
DIM = "\033[2m" if _TTY else ""
RESET = "\033[0m" if _TTY else ""


def main() -> None:
    db = Database()
    customer = db.run_query(
        "SELECT first_name, last_name FROM customers WHERE customer_id = ?",
        (DEMO_CUSTOMER_ID,),
    )
    if customer is None:
        print(f"Demo customer '{DEMO_CUSTOMER_ID}' not found. Run: make reset-db")
        sys.exit(1)

    first_name, last_name = customer
    print(
        f"\n{BOLD}{MAGENTA}Demo customer: {first_name} {last_name}{RESET}"
        f"  {DIM}(id {DEMO_CUSTOMER_ID}){RESET}\n"
    )

    print(f"{BLUE}{BOLD}Policies{RESET}")
    policies = db.run_query(
        """
        SELECT policy_type, policy_num, premium, coverage_limit, expiration_date
        FROM policies WHERE customer_id = ? ORDER BY policy_type
        """,
        (DEMO_CUSTOMER_ID,),
        one_record=False,
    )
    for policy_type, policy_num, premium, coverage_limit, expiration in policies or []:
        print(
            f"  {GREEN}{policy_type:<10}{RESET} {policy_num}  "
            f"premium ${premium:,.0f}  limit ${coverage_limit:,.0f}  "
            f"{DIM}expires {expiration}{RESET}"
        )

    print(f"\n{BLUE}{BOLD}Claims{RESET}")
    claims = db.run_query(
        """
        SELECT claim_id, policy_num, claim_date, claim_status
        FROM claims WHERE customer_id = ? ORDER BY claim_id
        """,
        (DEMO_CUSTOMER_ID,),
        one_record=False,
    )
    for claim_id, policy_num, claim_date, claim_status in claims or []:
        label = CLAIM_STATUS_LABELS.get(int(claim_status), "unknown")
        print(
            f"  {GREEN}{claim_id}{RESET}  policy {policy_num}  "
            f"status {claim_status} ({label})  {DIM}filed {claim_date}{RESET}"
        )

    print(f"\n{BLUE}{BOLD}Try saying{RESET}")
    print('  "What policies do I have?"')
    print('  "Check the status of claim CLAIM1236"')
    print('  "I need to file a claim on my car"')
    print('  "Does my homeowners policy cover flood damage?"')
    print()


if __name__ == "__main__":
    main()
