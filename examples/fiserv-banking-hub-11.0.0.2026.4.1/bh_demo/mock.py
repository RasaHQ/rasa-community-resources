# SPDX-License-Identifier: MIT
"""A local mock of four generic Banking Hub release operations.

It speaks the release's wire shape: POST paths, an EFXHeader header holding a
JSON object as a string, and JSON bodies. Every request is validated against the
learner-supplied pinned definitions, and every reply it builds is validated
against the same definitions before it is sent. All people, accounts, amounts
and dates are fictional and authored here. A mock proves our conversation design
and adapter; it never proves compatibility with any Fiserv system.

The labels it uses for an available balance ("Avail") and a next payment total
("Total") are the ones Fiserv's official Premier sample collection (R2026.3.3)
shows; the release itself declares no list. It carries no transaction history
and no payoff (see the README).
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

# Authored fictional data. Money is kept in cents; the wire carries JSON numbers.
ACCOUNTS = {
    "5550010001": {"type": "DDA", "party": "PARTY-A", "avail": 125000, "ledger": 127500},
    "5550010002": {"type": "SDA", "party": "PARTY-A", "avail": 540000, "ledger": 540000},
    "5550019001": {"type": "LOAN", "party": "PARTY-A", "next_date": "2026-12-01",
                   "principal": 15200, "interest": 3040, "total": 18240},
    "5550020001": {"type": "DDA", "party": "PARTY-B", "avail": 80000, "ledger": 80000},
    "5550020002": {"type": "SDA", "party": "PARTY-B", "avail": 5000, "ledger": 5000},
    "5550029001": {"type": "LOAN", "party": "PARTY-B", "next_date": "2026-12-10",
                   "principal": 8000, "interest": 1100, "total": 9100},
}


def _amount(cents: int) -> dict:
    return {"Amt": cents / 100, "CurCode": {"CurCodeType": "ISO4217-Alpha", "CurCodeValue": "USD"}}


def status(code="0", description="Success", severity="Info"):
    """EFX status codes from Fiserv's published Banking Hub response-codes page."""
    return {"StatusCode": code, "StatusDesc": description, "Severity": severity,
            "SvcProviderName": PROVIDER}


class BankingHubMock:
    def __init__(self, contract: BankingHubContract, *, fault: str = "none"):
        if fault not in {"none", "transfer-response-lost"}:
            raise ValueError("unknown fault")
        self.contract, self.fault = contract, fault
        self.accounts = {key: dict(value) for key, value in ACCOUNTS.items()}
        self.lock = Lock()
        self.calls = 0
        self.transfers = 0

    def _party(self, body):
        party = body["PartyAcctRelSel"].get("PartyKeys", {}).get("PartyId")
        rows = [{"PartyAcctRelKeys": {"PartyKeys": {"PartyId": party},
                                       "AcctKeys": {"AcctId": ident, "AcctType": account["type"]}},
                 "PartyAcctRelInfo": {},
                 "PartyAcctRelStatus": {"PartyAcctRelStatusCode": "Valid"}}
                for ident, account in sorted(self.accounts.items()) if account["party"] == party]
        if not rows:
            return 200, {"Status": status("1120", "No records match the selection criteria")}
        return 200, {"Status": status(), "RecCtrlOut": {"SentRecCount": len(rows)},
                     "PartyAcctRelRec": rows}

    def _account(self, body):
        keys = body["AcctSel"]["AcctKeys"]
        account = self.accounts.get(keys.get("AcctId"))
        if account is None or account["type"] != keys.get("AcctType"):
            return 404, {"Status": status("1121", "No records found", "Error")}
        record = {"AcctKeys": {"AcctId": keys["AcctId"], "AcctType": account["type"]},
                  "AcctStatus": {"AcctStatusCode": MOCK_ACCOUNT_STATUS}}
        if account["type"] in {"DDA", "SDA"}:
            record["DepositAcctInfo"] = {"AcctBal": [
                {"BalType": "Ledger", "CurAmt": _amount(account["ledger"])},
                {"BalType": "Avail", "CurAmt": _amount(account["avail"])}]}
        else:
            record["LoanAcctInfo"] = {"NextPmt": {"PmtDt": account["next_date"], "PmtCompositeAmt": [
                {"CompositeCurAmtType": "Principal", "CurAmt": _amount(account["principal"])},
                {"CompositeCurAmtType": "Interest", "CurAmt": _amount(account["interest"])},
                {"CompositeCurAmtType": "Total", "CurAmt": _amount(account["total"])}]}}
        return 200, {"Status": status(), "AcctRec": record}

    def _transfer(self, body):
        info = body["XferInfo"]
        if (info.get("IsValidateOnly") is True or "RecurModel" in info
                or "TransferType" in info):  # this example always omits it
            return 400, {"Status": status("1020", "Unsupported transfer request", "Error")}
        source_keys, target_keys = info["FromAcctRef"]["AcctKeys"], info["ToAcctRef"]["AcctKeys"]
        source = self.accounts.get(source_keys.get("AcctId"))
        target = self.accounts.get(target_keys.get("AcctId"))
        amount = round(info["CurAmt"]["Amt"] * 100)
        if (source is None or target is None or source["type"] != "DDA"
                or target["type"] not in {"DDA", "SDA"}
                or source_keys.get("AcctType") != source["type"]
                or target_keys.get("AcctType") != target["type"]
                or source["party"] != target["party"] or amount <= 0
                or info["CurAmt"]["CurCode"]["CurCodeValue"] != "USD"
                or source_keys["AcctId"] == target_keys["AcctId"] or amount > source["avail"]):
            return 422, {"Status": status("1020", "Transfer not permitted", "Error")}
        for account, sign in ((source, -1), (target, 1)):
            account["avail"] += sign * amount
            account["ledger"] += sign * amount
        self.transfers += 1
        return 201, {"Status": status(), "XferStatusRec": {
            "XferKeys": {"XferId": "FICTIONAL-XFER-" + str(self.transfers)},
            "XferStatus": {"XferStatusCode": "Valid"}}}

    def handle(self, path: str, header_value: str | None, raw: bytes):
        """Return (status, body, drop_connection)."""
        routes = {self.contract.path(key): key for key in ("party", "acct", "xfer")}
        key = routes.get(path)
        if key is None:
            return 404, {"Status": status("400", "Function not available", "Error")}, False
        try:
            body = json.loads(raw)
            self.contract.validate_header(key, header_value or "")
            self.contract.validate_request(key, body)
        except (ContractError, ValueError, TypeError, AttributeError):
            return 400, {"Status": status("1020", "Required element not included", "Error")}, False
        with self.lock:
            self.calls += 1
            code, response = {"party": self._party, "acct": self._account, "xfer": self._transfer}[key](body)
            if key == "xfer" and code == 201 and self.fault == "transfer-response-lost":
                return 0, None, True  # the transfer happened; the reply never arrives
            self.contract.validate_response(key, code, response)  # self-check, every reply
            return code, response, False


def serve(mock: BankingHubMock, sock) -> ThreadingHTTPServer:
    """Serve on an already-bound loopback socket; returns the running server."""

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):  # noqa: N802
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(min(length, 65536))
            try:
                code, body, drop = mock.handle(self.path, self.headers.get("EFXHeader"), raw)
            except ContractError:
                code, body, drop = 500, {"Status": status("999", "Unidentified error", "Error")}, False
            if drop:
                self.close_connection = True
                self.connection.close()
                return
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
