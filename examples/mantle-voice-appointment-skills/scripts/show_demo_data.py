#!/usr/bin/env python3
"""Print the demo patient's clinic data — the presenter's cheat sheet.

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

from lib.appointments import describe_slot, query_slots
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
        print(f"Demo patient '{DEMO_USERNAME}' not found. Run: make reset-db")
        sys.exit(1)

    profile = db.run_query(
        "SELECT patient_id, email, phone FROM users WHERE id = ?", (user_id,)
    )
    patient_id = profile[0] if profile else "unknown"
    print(f"\n{BOLD}{MAGENTA}🩺 Demo patient: {DEMO_USERNAME}{RESET}"
          f"  {DIM}(patient {patient_id}, Clinic of Rasa){RESET}\n")

    print(f"{BLUE}{BOLD}Contacts{RESET}")
    contacts = db.run_query(
        "SELECT name, handle, relationship FROM contacts WHERE user_id = ? ORDER BY name",
        (user_id,),
        one_record=False,
    )
    if contacts:
        for name, handle, relationship in contacts:
            print(f"  {GREEN}{name:<10}{RESET} {handle:<14} {DIM}{relationship}{RESET}")
    else:
        print(f"  {DIM}none saved{RESET}")

    print(f"\n{BLUE}{BOLD}Appointments{RESET}")
    appointments = db.run_query(
        """
        SELECT slot, doctor, visit_reason, status, reference
        FROM appointments WHERE user_id = ? ORDER BY created_at
        """,
        (user_id,),
        one_record=False,
    )
    if appointments:
        for slot, doctor, visit_reason, status, reference in appointments:
            print(f"  {GREEN}{describe_slot(slot)}{RESET}")
            print(f"      {doctor}  {DIM}{visit_reason} · {status} · {reference}{RESET}")
    else:
        print(f"  {DIM}none booked yet — book one during the demo{RESET}")

    print(f"\n{BLUE}{BOLD}Next open slots{RESET}  {DIM}(generated, not stored){RESET}")
    for slot in query_slots(preferred_doctor="any")[:3]:
        print(f"  {GREEN}{describe_slot(slot)}{RESET}  {DIM}{slot}{RESET}")

    print(f"\n{BLUE}{BOLD}Try saying{RESET}")
    print('  "What are your opening hours?"')
    print('  "Who is on my contact list?"')
    if contacts:
        print(f'  "Remove {contacts[0][1]} from my contacts"')
    print('  "I need to see a doctor next week"')
    print('  "I need an urgent appointment with Doctor Patel"')
    print('  "Save my doctor to my contacts"')
    print('  "Can someone from the clinic call me back?"')
    print()


if __name__ == "__main__":
    main()
