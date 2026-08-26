"""A small HubSpot CRM v3 client.

Everything the agent knows about a customer comes through here, so this module
is where the awkward parts of talking to someone else's system live: timeouts,
authentication failures, rate limits, and the difference between "no such
customer" and "the CRM is down".

The agent must be able to tell those apart. A skill that cannot reach HubSpot
should say so; a skill that reached HubSpot and found nobody should say that
instead. Both are returned as structured results rather than raised, so the
tool layer can hand the model a fact it can act on.

Base URL is configurable so the tutorial runs against the bundled mock CRM
without a HubSpot account. The code path is identical either way.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import httpx

DEFAULT_BASE_URL = "https://api.hubapi.com"
TIMEOUT_SECONDS = 10.0


class CrmError(Exception):
    """A CRM call that could not produce an answer.

    `reason` is a stable machine string the tools turn into a `ToolResult`, so
    the model branches on the reason rather than on prose that might change.
    """

    def __init__(self, reason: str, detail: str = "") -> None:
        super().__init__(detail or reason)
        self.reason = reason
        self.detail = detail


@dataclass(frozen=True)
class Contact:
    id: str
    email: str
    first_name: str
    last_name: str
    company: str

    @property
    def full_name(self) -> str:
        return " ".join(part for part in (self.first_name, self.last_name) if part)


def _base_url() -> str:
    return os.environ.get("HUBSPOT_BASE_URL", DEFAULT_BASE_URL).rstrip("/")


def _token() -> str:
    token = os.environ.get("HUBSPOT_ACCESS_TOKEN", "").strip()
    if not token:
        raise CrmError(
            "crm_not_configured",
            "HUBSPOT_ACCESS_TOKEN is not set. See .env.example.",
        )
    return token


async def _request(method: str, path: str, **kwargs: Any) -> dict:
    """One HTTP call, with every failure mapped to a CrmError reason."""
    headers = {
        "Authorization": f"Bearer {_token()}",
        "Content-Type": "application/json",
    }
    url = f"{_base_url()}{path}"
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
            response = await client.request(method, url, headers=headers, **kwargs)
    except httpx.TimeoutException as exc:
        raise CrmError("crm_timeout", f"{url} did not respond in {TIMEOUT_SECONDS}s") from exc
    except httpx.HTTPError as exc:
        raise CrmError("crm_unreachable", str(exc)) from exc

    if response.status_code == 401:
        # The token is missing, malformed, or revoked.
        raise CrmError("crm_auth_failed", "HubSpot rejected the access token")
    if response.status_code == 403:
        # The token is valid but the private app lacks the scope for this call.
        # Worth separating: one means "fix the token", the other "tick a box".
        raise CrmError("crm_forbidden", f"token lacks the scope for {path}")
    if response.status_code == 429:
        raise CrmError("crm_rate_limited", "HubSpot rate limit reached")
    if response.status_code == 404:
        raise CrmError("not_found", f"{path} returned 404")
    if response.status_code >= 400:
        raise CrmError("crm_error", f"HubSpot returned {response.status_code}")

    if not response.content:
        return {}
    try:
        return response.json()
    except ValueError as exc:
        raise CrmError("crm_error", "HubSpot returned a non-JSON body") from exc


def _to_contact(record: dict) -> Contact:
    props = record.get("properties") or {}
    return Contact(
        id=str(record.get("id", "")),
        email=props.get("email") or "",
        first_name=props.get("firstname") or "",
        last_name=props.get("lastname") or "",
        company=props.get("company") or "",
    )


async def find_contact_by_email(email: str) -> Contact | None:
    """Search HubSpot for one contact. Returns None when nobody matches."""
    payload = {
        "filterGroups": [
            {
                "filters": [
                    {"propertyName": "email", "operator": "EQ", "value": email}
                ]
            }
        ],
        "properties": ["email", "firstname", "lastname", "company"],
        "limit": 1,
    }
    data = await _request("POST", "/crm/v3/objects/contacts/search", json=payload)
    results = data.get("results") or []
    return _to_contact(results[0]) if results else None


async def open_tickets_for(contact_id: str) -> list[dict]:
    """Tickets associated with a contact, newest first."""
    data = await _request(
        "GET",
        f"/crm/v3/objects/contacts/{contact_id}/associations/tickets",
        params={"limit": 20},
    )
    ticket_ids = [item["toObjectId"] for item in (data.get("results") or [])]
    tickets = []
    for ticket_id in ticket_ids:
        record = await _request(
            "GET",
            f"/crm/v3/objects/tickets/{ticket_id}",
            params={"properties": "subject,hs_pipeline_stage,createdate"},
        )
        props = record.get("properties") or {}
        tickets.append(
            {
                "id": str(record.get("id", "")),
                "subject": props.get("subject") or "(no subject)",
                "stage": props.get("hs_pipeline_stage") or "unknown",
                "created": (props.get("createdate") or "")[:10],
            }
        )
    return tickets


async def log_note(contact_id: str, body: str) -> str:
    """Write a note onto the contact's timeline. Returns the new note id."""
    payload = {
        "properties": {"hs_note_body": body, "hs_timestamp": _now_iso()},
        "associations": [
            {
                "to": {"id": contact_id},
                "types": [
                    {
                        "associationCategory": "HUBSPOT_DEFINED",
                        # 202 = note-to-contact, from HubSpot's association types.
                        "associationTypeId": 202,
                    }
                ],
            }
        ],
    }
    data = await _request("POST", "/crm/v3/objects/notes", json=payload)
    return str(data.get("id", ""))


def _now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace(
        "+00:00", "Z"
    )
