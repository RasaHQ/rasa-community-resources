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

from .client import SilverLakeClient, Unavailable, UnknownOutcome
from .contract import SilverLakeContract
from .mock import SilverLakeMock

# One call per operation, on the authored fictional data in mock.py.
PROBES = (
    ("AcctSrch", lambda client: client.accounts("C100001")),
    ("AcctBalInq", lambda client: client.available_balance("1001001", "D")),
    ("AcctHistSrch", lambda client: client.history("1001001", "D")),
    ("AcctInq", lambda client: client.loan_payment("7001001")),
    ("LnPayoffInq", lambda client: client.payoff("7001001", "2026-11-20")),
    ("XferAdd", lambda client: client.transfer(("1001001", "D"), ("1001002", "S"), Decimal("1.00"))),
)


def changed_operations(contract: SilverLakeContract) -> list[str]:
    """Names of the operations whose request or reply no longer fits the schemas."""
    mock = SilverLakeMock(contract)  # fresh in-memory state; nothing leaves the process

    def respond(request: httpx.Request) -> httpx.Response:
        status, body, _ = mock.handle(request.headers.get("SOAPAction"), request.content)
        return httpx.Response(status or 500, content=body)

    client = SilverLakeClient(contract, "http://127.0.0.1:9", transport=httpx.MockTransport(respond))
    changed = []
    for name, call in PROBES:
        try:
            call(client)
        except (Unavailable, UnknownOutcome):
            changed.append(name + " request or reply no longer fits the schemas")
    return changed
