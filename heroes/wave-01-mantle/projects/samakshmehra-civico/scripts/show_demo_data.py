#!/usr/bin/env python3
"""Print what the agent knows, so a demo can be driven from real values."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib import directory, store  # noqa: E402


def main() -> None:
    d = directory._directory()
    print(f"\n{d['municipality']} — helpline {d['helpline']}")
    print("This is demo data. Nothing here reaches a municipal system.\n")

    print("CATEGORIES")
    for key, route in store.routing().items():
        print(f"  {key:14} {route['department']:18} target {route['sla_days']} days")

    print("\nWARD DIRECTORY")
    by_zone: dict[str, list] = {}
    for row in d["wards"]:
        by_zone.setdefault(row["zone"], []).append(row)
    for zone, rows in by_zone.items():
        print(f"  {zone}")
        for row in rows:
            print(f"    {row['locality']:22} {row['pincode']}  "
                  f"{row['ward_id']}  {row['officer_name']}")

    print("\nSEEDED COMPLAINTS")
    seen = set()
    for citizen in [{"phone": "9876543210"}, {"phone": "9812345678"}]:
        for row in store.complaints_for_phone(citizen["phone"]):
            if row["complaint_id"] in seen:
                continue
            seen.add(row["complaint_id"])
            if row["is_overdue"]:
                when = f"{row['days_overdue']} days OVERDUE"
            elif row["is_open"]:
                when = f"{row['days_left']} days left"
            else:
                when = "closed"
            print(f"  {row['complaint_id']}  {row['category']:13} "
                  f"{row['locality']:12} {row['status']:11} {when}")
            print(f"            say: \"{row['spoken_id']}\"")

    print("\nDEMO CALLERS")
    for c in [store.citizen_by_phone("9876543210"), store.citizen_by_phone("9812345678")]:
        print(f"  {c['phone']}  {c['name']}")
    print("  9000000000  (unrecognised — make demo-unknown)")

    print("\nTRY SAYING")
    for line in [
        "There is a huge pothole in Vaishali",
        "The drain is blocked in Vaishali          (finds the open CIV1004)",
        "It is near my house                       (unmappable — two tries, then the cell)",
        "My property tax is wrong                  (out of scope)",
        "What happened to C I V one zero zero two? (overdue — offers escalation)",
        "Who handles garbage in Indirapuram?       (answers, files nothing)",
    ]:
        print(f"  {line}")
    print()


if __name__ == "__main__":
    main()
