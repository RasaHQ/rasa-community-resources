# SPDX-License-Identifier: MIT
"""A local mock of two generic Banking Hub release operations.

It speaks the release's wire shape: POST paths, an EFXHeader header holding a
JSON object as a string, and JSON bodies. Every request is validated against the
learner-supplied pinned definitions, and every reply it builds is validated
against the same definitions before it is sent. All people, accounts and dates
are fictional and authored here. A mock proves our conversation design and
adapter; it never proves compatibility with any Fiserv system.

It answers only what the release lets us state with a sourced value: account
relationships and a loan's next payment date. It deliberately carries no
balance, payment amount, payoff or transfer, because the codes that would label
those values are not declared in the release (see the README).
"""
from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from threading import Lock, Thread

from .contract import ContractError, BankingHubContract

MOCK_ORGANIZATION = "FICTIONAL-MOCK-ORG"
PROVIDER = "FictionalMockBankingHub"
# AcctStatusCode is required by the release but has no declared values. The mock
# sends this clearly fictional placeholder; the client never reads it.
MOCK_ACCOUNT_STATUS = "FictionalMockStatus"

ACCOUNTS = {
    "5550010001": {"type": "DDA", "party": "PARTY-A"},
    "5550010002": {"type": "SDA", "party": "PARTY-A"},
    "5550019001": {"type": "LOAN", "party": "PARTY-A", "next_date": "2026-12-01"},
    "5550020001": {"type": "DDA", "party": "PARTY-B"},
    "5550020002": {"type": "SDA", "party": "PARTY-B"},
    "5550029001": {"type": "LOAN", "party": "PARTY-B", "next_date": "2026-12-10"},
}


def status(code="0", description="Success", severity="Info"):
    """EFX status codes from Fiserv's published Banking Hub response-codes page."""
    return {"StatusCode": code, "StatusDesc": description, "Severity": severity,
            "SvcProviderName": PROVIDER}


class BankingHubMock:
    def __init__(self, contract: BankingHubContract):
        self.contract = contract
        self.lock = Lock()
        self.calls = 0

    def _party(self, body):
        party = body["PartyAcctRelSel"].get("PartyKeys", {}).get("PartyId")
        rows = [{"PartyAcctRelKeys": {"PartyKeys": {"PartyId": party},
                                       "AcctKeys": {"AcctId": ident, "AcctType": account["type"]}},
                 "PartyAcctRelInfo": {},
                 "PartyAcctRelStatus": {"PartyAcctRelStatusCode": "Valid"}}
                for ident, account in sorted(ACCOUNTS.items()) if account["party"] == party]
        if not rows:
            return 200, {"Status": status("1120", "No records match the selection criteria")}
        return 200, {"Status": status(), "RecCtrlOut": {"SentRecCount": len(rows)},
                     "PartyAcctRelRec": rows}

    def _account(self, body):
        keys = body["AcctSel"]["AcctKeys"]
        account = ACCOUNTS.get(keys.get("AcctId"))
        if account is None or account["type"] != keys.get("AcctType"):
            return 404, {"Status": status("1121", "No records found", "Error")}
        record = {"AcctKeys": {"AcctId": keys["AcctId"], "AcctType": account["type"]},
                  "AcctStatus": {"AcctStatusCode": MOCK_ACCOUNT_STATUS}}
        if account["type"] == "LOAN":
            record["LoanAcctInfo"] = {"NextPmt": {"PmtDt": account["next_date"]}}
        return 200, {"Status": status(), "AcctRec": record}

    def handle(self, path: str, header_value: str | None, raw: bytes):
        """Return (status, body)."""
        routes = {self.contract.path("party"): "party", self.contract.path("acct"): "acct"}
        key = routes.get(path)
        if key is None:
            return 404, {"Status": status("400", "Function not available", "Error")}
        try:
            body = json.loads(raw)
            self.contract.validate_header(key, header_value or "")
            self.contract.validate_request(key, body)
        except (ContractError, ValueError, TypeError, AttributeError):
            return 400, {"Status": status("1020", "Required element not included", "Error")}
        with self.lock:
            self.calls += 1
            code, response = self._party(body) if key == "party" else self._account(body)
            self.contract.validate_response(key, code, response)  # self-check, every reply
            return code, response


def serve(mock: BankingHubMock, sock) -> ThreadingHTTPServer:
    """Serve on an already-bound loopback socket; returns the running server."""

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):  # noqa: N802
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(min(length, 65536))
            try:
                code, body = mock.handle(self.path, self.headers.get("EFXHeader"), raw)
            except ContractError:
                code, body = 500, {"Status": status("999", "Unidentified error", "Error")}
            payload = json.dumps(body).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, *args):  # no access log: nothing sensitive to print
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler, bind_and_activate=False)
    server.socket.close()
    server.socket = sock
    server.server_address = sock.getsockname()
    Thread(target=server.serve_forever, daemon=True).start()
    return server
