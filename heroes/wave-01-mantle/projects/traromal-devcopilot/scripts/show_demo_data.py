#!/usr/bin/env python3
"""Print the demo developer's data — the presenter's cheat sheet.

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

from lib.database import (  # noqa: E402
    DEMO_BADGE_CODE,
    DEMO_FIRST_NAME,
    DEMO_LAST_NAME,
    DEMO_TECH_ID,
    PRIORITY_LABELS,
    Database,
)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

_TTY = sys.stdout.isatty()
GREEN = "\033[92m" if _TTY else ""
BLUE = "\033[94m" if _TTY else ""
MAGENTA = "\033[95m" if _TTY else ""
BOLD = "\033[1m" if _TTY else ""
DIM = "\033[2m" if _TTY else ""
RESET = "\033[0m" if _TTY else ""


def main() -> None:
    db = Database()
    tech = db.run_query(
        "SELECT first_name, last_name FROM technicians WHERE tech_id = ?",
        (DEMO_TECH_ID,),
    )
    if tech is None:
        print(f"Demo developer '{DEMO_TECH_ID}' not found. Run: make reset-db")
        sys.exit(1)

    first_name, last_name = tech
    print(
        f"\n{BOLD}{MAGENTA}Demo developer: {first_name} {last_name}{RESET}"
        f"  {DIM}(id {DEMO_TECH_ID}, badge {DEMO_BADGE_CODE}){RESET}\n"
    )

    print(f"{BLUE}{BOLD}Assigned tasks{RESET}")
    calls = db.run_query(
        """
        SELECT call_ref, building, unit_id, priority, status, sla_minutes
        FROM service_calls WHERE tech_id = ? ORDER BY
            CASE priority WHEN 'emergency' THEN 0 WHEN 'standard' THEN 1 ELSE 2 END,
            scheduled_at
        """,
        (DEMO_TECH_ID,),
        one_record=False,
    )
    for call_ref, building, unit_id, priority, status, sla_minutes in calls or []:
        label = PRIORITY_LABELS.get(priority, priority)
        print(
            f"  {GREEN}{call_ref}{RESET}  {building}  "
            f"{label}  {DIM}{status}, SLA {sla_minutes}m{RESET}"
        )

    print(f"\n{BLUE}{BOLD}Support tickets{RESET}")
    tickets = db.run_query(
        """
        SELECT ticket_id, summary, severity, status FROM support_tickets
        WHERE tech_id = ? ORDER BY
            CASE severity WHEN 'critical' THEN 0 WHEN 'high' THEN 1
            WHEN 'medium' THEN 2 ELSE 3 END
        """,
        (DEMO_TECH_ID,),
        one_record=False,
    )
    for ticket_id, summary, severity, status in tickets or []:
        print(
            f"  {GREEN}{ticket_id}{RESET}  {summary}  "
            f"{DIM}{severity}, {status}{RESET}"
        )

    print(f"\n{BLUE}{BOLD}Hardware & licenses{RESET}")
    parts = db.run_query(
        "SELECT part_no, part_name, unit_price, qty_on_hand, restricted FROM parts",
        one_record=False,
    )
    for part_no, part_name, unit_price, qty_on_hand, restricted in parts or []:
        flag = "  [APPROVAL]" if restricted else ""
        print(
            f"  {GREEN}{part_no}{RESET}  {part_name}  "
            f"{DIM}£{unit_price:.0f}, stock {qty_on_hand}{RESET}{flag}"
        )

    print(f"\n{BLUE}{BOLD}Try saying{RESET}")
    print('  "What am I working on today?"')
    print('  "Give me a briefing"')
    print('  "Do my standup"')
    print('  "Mark T K T one zero zero three done"')
    print('  "The auth service keeps returning 500 and it is driving me insane"')
    print('  "I need a mechanical keyboard"')
    print('  "Deploy auth-service to staging"')
    print('  "Any PRs waiting on me?"')
    print('  "Remind me to check the prod logs in 30 minutes"')
    print('  "Brief the next on-call engineer"')
    print()


if __name__ == "__main__":
    main()
