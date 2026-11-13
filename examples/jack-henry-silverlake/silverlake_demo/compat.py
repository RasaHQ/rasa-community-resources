# SPDX-License-Identifier: MIT
"""Does a newer Jack Henry archive still fit everything this example uses?

Jack Henry may republish the archive. When its bytes differ from the pinned
ones (see VENDOR-FILES.md), this check runs each of the six operations the
example uses through its own client and its own mock, in memory and against
the supplied schemas: every request the example sends and every reply it reads
is validated element by element. If all six still validate, the example can
start. If one fails, it is named. This checks shape, not meaning.
"""
from __future__ import annotations

from decimal import Decimal

import httpx

from .client import SilverLakeClient
from .contract import SilverLakeContract
from .mock import SilverLakeMock

# One call per operation on the authored fictional data in mock.py, each with the
# exact result it must give. A probe that returns anything else, or raises
# anything at all, names its operation: a method that falls back to a refusal or
# an "unavailable" value (rather than raising) cannot hide a change.
PROBES = (
    ("AcctSrch", lambda client: client.accounts("C100001"),
     [("1001001", "D"), ("1001002", "S"), ("7001001", "L")]),
    ("AcctBalInq", lambda client: client.available_balance("1001001", "D"), "1250.00"),
    ("AcctHistSrch", lambda client: client.history("1001001", "D"),
     ([{"date": "2026-11-04", "amount": "42.00", "direction": "debit", "currency": "USD"},
       {"date": "2026-11-03", "amount": "900.00", "direction": "credit", "currency": "USD"},
       {"date": "2026-11-01", "amount": "15.50", "direction": "debit", "currency": "USD"}], "3")),
    ("AcctInq", lambda client: client.loan_payment("7001001"),
     {"amount_due": "242.40", "next_due_date": "2026-12-01", "currency": "USD"}),
    ("LnPayoffInq", lambda client: client.payoff("7001001", "2026-11-20"),
     {"as_of": "2026-11-20", "amount": "4120.55", "currency": "USD"}),
    ("XferAdd", lambda client: client.transfer(("1001001", "D"), ("1001002", "S"), Decimal("1.00")), "accepted"),
)


def changed_operations(contract: SilverLakeContract) -> list[str]:
    """Names of the operations whose request or reply no longer fits the schemas."""
    mock = SilverLakeMock(contract)  # fresh in-memory state; nothing leaves the process

    def respond(request: httpx.Request) -> httpx.Response:
        status, body, _ = mock.handle(request.headers.get("SOAPAction"), request.content)
        return httpx.Response(status or 500, content=body)

    client = SilverLakeClient(contract, "http://127.0.0.1:9", transport=httpx.MockTransport(respond))
    changed = []
    for name, call, expected in PROBES:
        try:
            fits = call(client) == expected
        except Exception:  # any failure at all counts as a change, never a traceback
            fits = False
        if not fits:
            changed.append(name + " request or reply no longer fits the schemas")
    return changed
