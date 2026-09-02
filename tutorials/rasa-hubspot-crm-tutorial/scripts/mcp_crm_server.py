#!/usr/bin/env python3
"""A local MCP server exposing the same three CRM tools over MCP.

This is the remote end of the transport swap. It publishes `find_contact_by_email`,
`list_open_tickets`, and `add_timeline_note` as MCP tools with the same names and
the same argument shapes the local `@tool` functions had, so the skills that
import them do not have to be rewritten.

    python scripts/mcp_crm_server.py            # serves on 127.0.0.1:8931/mcp

It talks to the CRM through `lib/hubspot.py` — the same client the REST version
uses, unchanged. Pointed at `scripts/mock_hubspot.py` it needs no HubSpot account
and no network beyond loopback.

WHY HTTP AND NOT STDIO
----------------------
Mantle connects to MCP servers over streamable HTTP only. `MCPServerSpec` in
`rasa/mantle/config/integrations.py` requires a `url:` whose scheme is `http` or
`https` and rejects anything else, and `MCPServerConnection._run_lifecycle` in
`rasa/shared/utils/mcp/server_connection.py` builds a `streamablehttp_client`
with no stdio branch. A stdio server cannot be reached by this engine at all.
Loopback HTTP is the credential-free equivalent: no account, no billing, and no
packet leaves the machine.
"""

from __future__ import annotations

import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

from dotenv import load_dotenv  # noqa: E402

load_dotenv(os.path.join(_ROOT, ".env"))

from mcp.server.fastmcp import FastMCP  # noqa: E402
from pydantic import BaseModel  # noqa: E402

from lib.hubspot import (  # noqa: E402
    CrmError,
    find_contact_by_email as _find,
    log_note,
    open_tickets_for,
)

HOST, PORT = "127.0.0.1", 8931

mcp = FastMCP("hubspot-crm", host=HOST, port=PORT, stateless_http=True)


# WHY THESE RETURN MODELS EXIST — a real finding, caught by scripts/prove_mcp_swap.py.
#
# A tool annotated `-> dict` publishes NO outputSchema, so FastMCP sends the
# result as unstructured text and `CallToolResult.structuredContent` is None.
# Mantle notices: `MCPRuntime._invoke_mcp_tool` uses structuredContent when it
# is present and otherwise falls back to dumping the content blocks, so the
# model would receive a JSON string wrapped in a list of text parts instead of
# the flat object the local `@tool` returned.
#
# The skill instructions branch on `ok` and `error`. Those names have to
# survive the wire for the prose to keep working — which is the whole claim.
# An explicit return model is what makes them survive: it publishes an
# outputSchema, so structuredContent comes back populated and the payload the
# model sees is the same shape the REST tool produced.
#
# `extra="allow"` keeps the error variants ( {"ok": false, "error": ...} )
# expressible through the same model.
class CrmResult(BaseModel):
    """Flat result object, mirroring what the local @tool returned."""

    model_config = {"extra": "allow"}

    ok: bool


@mcp.tool(
    description=(
        "Find the customer in the CRM by their email address. "
        "Call this before discussing anything about their account."
    )
)
async def find_contact_by_email(email: str) -> CrmResult:
    """Look the caller up in HubSpot.

    Args:
        email: The customer's email address.
    """
    try:
        contact = await _find(email)
    except CrmError as exc:
        return CrmResult(ok=False, error=exc.reason)

    if contact is None:
        # Not an error: the CRM answered, and nobody matches.
        return CrmResult(ok=False, error="contact_not_found", email=email)

    return CrmResult(
        ok=True,
        contact_id=contact.id,
        name=contact.full_name,
        company=contact.company,
    )


@mcp.tool(description="List the support tickets on the identified customer's account.")
async def list_open_tickets(contact_id: str) -> CrmResult:
    """Read the caller's tickets from the CRM.

    Args:
        contact_id: HubSpot contact id of the identified customer.
    """
    # `contact_id` is a PARAMETER here, not a memory read. An MCP tool has no
    # ToolContext, so the value has to travel as an argument. See the README
    # section "What MCP does not do for you".
    if not contact_id:
        return CrmResult(ok=False, error="not_identified")
    try:
        tickets = await open_tickets_for(str(contact_id))
    except CrmError as exc:
        return CrmResult(ok=False, error=exc.reason)
    return CrmResult(ok=True, count=len(tickets), tickets=tickets)


@mcp.tool(
    description="Save a short summary of this conversation to the customer's CRM timeline."
)
async def add_timeline_note(contact_id: str, summary: str) -> CrmResult:
    """Write a note onto the customer's CRM record.

    Args:
        contact_id: HubSpot contact id of the identified customer.
        summary: One or two sentences describing what the caller wanted.
    """
    if not contact_id:
        return CrmResult(ok=False, error="not_identified")
    try:
        note_id = await log_note(str(contact_id), summary)
    except CrmError as exc:
        # A failed write is the dangerous one: never let the agent claim it
        # saved something that is not there.
        return CrmResult(ok=False, error=exc.reason)
    return CrmResult(ok=True, note_id=note_id)


if __name__ == "__main__":
    print(f"MCP CRM server listening on http://{HOST}:{PORT}/mcp", flush=True)
    print("  tools: find_contact_by_email, list_open_tickets, add_timeline_note", flush=True)
    print("  stop with Ctrl-C", flush=True)
    mcp.run(transport="streamable-http")
