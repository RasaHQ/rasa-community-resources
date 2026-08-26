#!/usr/bin/env python3
"""A tiny stand-in for HubSpot CRM v3, so the tutorial runs with no account.

It speaks the real request and response shapes for the three endpoints this
agent uses, including the 401 body HubSpot actually returns. The agent code does
not know the difference — only HUBSPOT_BASE_URL changes.

    python scripts/mock_hubspot.py          # serves on 127.0.0.1:8787

Deliberately stdlib-only and in-memory: it should start instantly and leave
nothing behind.
"""

from __future__ import annotations

import json
import re
from http.server import BaseHTTPRequestHandler, HTTPServer

HOST, PORT = "127.0.0.1", 8787

CONTACTS = [
    {
        "id": "701",
        "properties": {
            "email": "dana.okafor@example.com",
            "firstname": "Dana",
            "lastname": "Okafor",
            "company": "Okafor Logistics",
        },
    },
    {
        "id": "702",
        "properties": {
            "email": "sam.rivera@example.com",
            "firstname": "Sam",
            "lastname": "Rivera",
            "company": "Rivera Foods",
        },
    },
]

TICKETS = {
    "701": [
        {
            "id": "9001",
            "properties": {
                "subject": "Invoice 4471 shows the wrong VAT rate",
                "hs_pipeline_stage": "waiting_on_us",
                "createdate": "2026-08-11T09:14:00Z",
            },
        },
        {
            "id": "9002",
            "properties": {
                "subject": "Add a second admin to the account",
                "hs_pipeline_stage": "waiting_on_contact",
                "createdate": "2026-08-19T15:02:00Z",
            },
        },
    ],
    "702": [],
}

NOTES: list[dict] = []


class Handler(BaseHTTPRequestHandler):
    def _send(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _authorised(self) -> bool:
        """Mirror HubSpot: anything without a bearer token is INVALID_AUTHENTICATION."""
        header = self.headers.get("Authorization", "")
        if header.startswith("Bearer ") and header[7:].strip():
            return True
        self._send(
            401,
            {
                "status": "error",
                "message": "Authentication credentials not found. This API supports "
                "OAuth 2.0 authentication and you can find more details at "
                "https://developers.hubspot.com/docs/methods/auth/oauth-overview",
                "correlationId": "00000000-0000-0000-0000-000000000000",
                "category": "INVALID_AUTHENTICATION",
            },
        )
        return False

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        if not self._authorised():
            return
        path = self.path.split("?")[0]

        match = re.fullmatch(r"/crm/v3/objects/contacts/(\d+)/associations/tickets", path)
        if match:
            tickets = TICKETS.get(match.group(1), [])
            self._send(
                200,
                {"results": [{"toObjectId": t["id"], "type": "contact_to_ticket"} for t in tickets]},
            )
            return

        match = re.fullmatch(r"/crm/v3/objects/tickets/(\d+)", path)
        if match:
            for tickets in TICKETS.values():
                for ticket in tickets:
                    if ticket["id"] == match.group(1):
                        self._send(200, ticket)
                        return
            self._send(404, {"status": "error", "category": "OBJECT_NOT_FOUND"})
            return

        self._send(404, {"status": "error", "category": "OBJECT_NOT_FOUND"})

    def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        if not self._authorised():
            return
        length = int(self.headers.get("Content-Length", 0))
        payload = json.loads(self.rfile.read(length) or b"{}")
        path = self.path.split("?")[0]

        if path == "/crm/v3/objects/contacts/search":
            wanted = ""
            for group in payload.get("filterGroups", []):
                for flt in group.get("filters", []):
                    if flt.get("propertyName") == "email":
                        wanted = (flt.get("value") or "").lower()
            found = [c for c in CONTACTS if c["properties"]["email"].lower() == wanted]
            self._send(200, {"total": len(found), "results": found})
            return

        if path == "/crm/v3/objects/notes":
            note_id = str(10_000 + len(NOTES))
            NOTES.append({"id": note_id, "payload": payload})
            self._send(201, {"id": note_id, "properties": payload.get("properties", {})})
            return

        self._send(404, {"status": "error", "category": "OBJECT_NOT_FOUND"})

    def log_message(self, *args) -> None:  # keep the tutorial output readable
        return


if __name__ == "__main__":
    # flush=True: without it the banner sits in the buffer when the output is
    # piped or captured, and the reader thinks nothing started.
    print(f"mock HubSpot CRM listening on http://{HOST}:{PORT}", flush=True)
    print("  contacts: dana.okafor@example.com, sam.rivera@example.com", flush=True)
    print("  stop with Ctrl-C", flush=True)
    HTTPServer((HOST, PORT), Handler).serve_forever()
