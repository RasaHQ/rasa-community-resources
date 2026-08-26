#!/usr/bin/env python3
"""Check the CRM connection and report exactly what the token can and cannot do.

Run this before the agent. It answers the two questions that otherwise cost an
hour: is the token working, and does it have the right scopes?

    make crm-check                      # against whatever .env points at
    make crm-check EMAIL=someone@x.com  # look up a specific contact

Each capability is probed independently, so a missing scope shows up as one
failed row naming the scope to add, rather than as a generic 403.
"""

from __future__ import annotations

import asyncio
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

# The rasa CLI loads the project .env for you (rasa.cli.project_env). This
# script runs outside that, so it does the same thing explicitly — otherwise it
# would report "not configured" while the agent works fine, which is exactly
# the confusion a diagnostic tool is supposed to remove.
from dotenv import load_dotenv  # noqa: E402

load_dotenv(os.path.join(_ROOT, ".env"))

from lib.hubspot import (  # noqa: E402
    CrmError,
    _base_url,
    find_contact_by_email,
    log_note,
    open_tickets_for,
)

GREEN, RED, YELLOW, DIM, RESET = (
    ("\033[92m", "\033[91m", "\033[93m", "\033[2m", "\033[0m")
    if sys.stdout.isatty()
    else ("", "", "", "", "")
)

# What to tell the reader when a capability fails, per HubSpot scope.
SCOPE_HINT = {
    "contacts": "crm.objects.contacts.read",
    "tickets": "tickets",
    "notes": "crm.objects.notes.write (or crm.objects.contacts.write on some plans)",
}

EMAIL = os.environ.get("EMAIL") or "dana.okafor@example.com"


def row(label: str, ok: bool | None, detail: str = "") -> None:
    mark = f"{GREEN}✓{RESET}" if ok else (f"{RED}✗{RESET}" if ok is False else f"{YELLOW}–{RESET}")
    print(f"  {mark} {label:<26} {detail}")


async def main() -> int:
    token = os.environ.get("HUBSPOT_ACCESS_TOKEN", "")
    base = _base_url()
    live = "hubapi.com" in base

    print()
    print(f"  base url  {base}  {DIM}({'real HubSpot' if live else 'mock CRM'}){RESET}")
    print(f"  token     {'set, ' + str(len(token)) + ' chars' if token else RED + 'NOT SET' + RESET}")
    print(f"  lookup    {EMAIL}")
    print()

    if not token:
        print(f"{RED}  No HUBSPOT_ACCESS_TOKEN. See SETUP.md step 3.{RESET}\n")
        return 1

    failures = 0

    # 1. Contacts ------------------------------------------------------------
    contact = None
    try:
        contact = await find_contact_by_email(EMAIL)
        if contact is None:
            row("read contacts", True, f"{DIM}reachable, no match for {EMAIL}{RESET}")
        else:
            row("read contacts", True, f"{contact.full_name} id={contact.id}")
    except CrmError as exc:
        failures += 1
        hint = f"{DIM}needs {SCOPE_HINT['contacts']}{RESET}" if exc.reason == "crm_forbidden" else ""
        row("read contacts", False, f"{exc.reason} {hint}")

        if exc.reason == "crm_auth_failed":
            print(f"\n{RED}  HubSpot rejected the token itself.{RESET}")
            print(f"{DIM}  Copy it again from Development → Legacy apps → your app → Auth.{RESET}")
            print(f"{DIM}  See SETUP.md step 3.{RESET}\n")
            return 1
        if exc.reason == "crm_forbidden":
            print(f"\n{RED}  The token is valid but the app is missing a scope.{RESET}")
            print(f"{DIM}  Add {SCOPE_HINT['contacts']} — SETUP.md step 2.{RESET}\n")
            return 1
        if exc.reason in {"crm_unreachable", "crm_timeout", "crm_not_configured"}:
            print(f"\n{RED}  Cannot reach the CRM at all — nothing else will work.{RESET}")
            if not live:
                print(f"{DIM}  Is the mock running? Start it with: make mock{RESET}")
            print()
            return 1

    if contact is None:
        print()
        print(f"{YELLOW}  No contact to test tickets or notes against.{RESET}")
        print(f"{DIM}  Re-run with a real address: make crm-check EMAIL=you@yourcompany.com{RESET}")
        print()
        return 1 if failures else 0

    # 2. Tickets -------------------------------------------------------------
    try:
        tickets = await open_tickets_for(contact.id)
        row("read tickets", True, f"{len(tickets)} found")
        for ticket in tickets:
            print(f"      {DIM}[{ticket['id']}] {ticket['stage']:<20} {ticket['subject']}{RESET}")
    except CrmError as exc:
        failures += 1
        tip = f"{DIM}needs {SCOPE_HINT['tickets']}{RESET}" if exc.reason == "crm_forbidden" else ""
        row("read tickets", False, f"{exc.reason} {tip}")

    # 3. Notes ---------------------------------------------------------------
    # This one writes. Say so, and make the note obviously a test.
    try:
        note_id = await log_note(contact.id, "Connection test from the Rasa tutorial. Safe to delete.")
        row("write notes", True, f"created note {note_id} {DIM}(delete it from the timeline){RESET}")
    except CrmError as exc:
        failures += 1
        tip = f"{DIM}needs {SCOPE_HINT['notes']}{RESET}" if exc.reason == "crm_forbidden" else ""
        row("write notes", False, f"{exc.reason} {tip}")

    print()
    if failures:
        print(f"{RED}  {failures} capability check(s) failed — see SETUP.md step 2 for scopes.{RESET}\n")
        return 1
    print(f"{GREEN}  All good. Run: make train, then make chat{RESET}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
