# SPDX-License-Identifier: MIT
"""A local mock of the five selected Banking Hub (Premier) operations.

It speaks the vendor's wire shape: POST paths, an EFXHeader header holding a
JSON object as a string, and JSON bodies. Every request is validated against the
learner-supplied pinned OpenAPI documents, and every response it builds is
validated against the same documents before it is sent. All people, accounts and
amounts are fictional and authored here. A mock proves our conversation design
and adapter; it never proves compatibility with Fiserv systems.
"""
from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from threading import Lock, Thread

from .contract import ContractError, PremierContract

MOCK_ORGANIZATION = "FICTIONAL-MOCK-ORG"
PROVIDER = "FictionalMockPremier"

# Authored fictional data. Money is kept in cents; the wire carries JSON numbers.
ACCOUNTS = {
    "5550010001": {"type": "DDA", "party": "PARTY-A", "avail": 125000, "ledger": 127500},
    "5550010002": {"type": "DDA", "party": "PARTY-A", "avail": 30000, "ledger": 30000},
    "5550019001": {"type": "LOAN", "party": "PARTY-A", "next_total": 18240,
                   "next_date": "2026-12-01", "payoff": 412055, "past_due": 6000, "pmt_due": 24240},
    "5550020001": {"type": "DDA", "party": "PARTY-B", "avail": 80000, "ledger": 80000},
    "5550020002": {"type": "DDA", "party": "PARTY-B", "avail": 5000, "ledger": 5000},
    "5550029001": {"type": "LOAN", "party": "PARTY-B", "next_total": 9100,
                   "next_date": "2026-12-10", "payoff": 150000, "past_due": 0, "pmt_due": 9100},
}
TRANSACTIONS = {
    "5550010001": [
        ("T-1005", "2026-11-04", "Debit", 4200, "Fictional Market"),
        ("T-1004", "2026-11-03", "Credit", 90000, "Fictional Payroll"),
        ("T-1003", "2026-11-01", "Debit", 1550, "Fictional Pharmacy"),
        ("T-1002", "2026-10-29", "Debit", 8000, "Fictional Gas Co"),
        ("T-1001", "2026-10-27", "Credit", 2500, "Fictional Refund"),
    ],
    "5550010002": [("T-2001", "2026-10-30", "Credit", 30000, "Fictional Transfer")],
    "5550020001": [("T-3001", "2026-11-02", "Credit", 80000, "Fictional Payroll")],
    "5550020002": [("T-4001", "2026-11-02", "Credit", 5000, "Fictional Deposit")],
}
PAGE = 3


def _amount(cents: int) -> dict:
    return {"Amt": cents / 100, "CurCode": {"CurCodeType": "ISO4217-Alpha", "CurCodeValue": "USD"}}


def _status(code="0", description="Success", severity="Info"):
    return {"StatusCode": code, "StatusDesc": description, "Severity": severity,
            "SvcProviderName": PROVIDER}


class PremierMock:
    def __init__(self, contract: PremierContract, *, fault: str = "none"):
        if fault not in {"none", "transfer-response-lost"}:
            raise ValueError("unknown fault")
        self.contract, self.fault = contract, fault
        self.accounts = {key: dict(value) for key, value in ACCOUNTS.items()}
        self.lock = Lock()
        self.transfers = 0

    # -- operations -----------------------------------------------------
    def _party(self, body):
        party = body["PartyAcctRelSel"].get("PartyKeys", {}).get("PartyId")
        rows = [{"PartyAcctRelKeys": {"PartyKeys": {"PartyId": party},
                                       "AcctKeys": {"AcctId": ident, "AcctType": account["type"]}},
                 "PartyAcctRelInfo": {"PartyRef": {"PartyKeys": {"PartyId": party}}},
                 "PartyAcctRelStatus": {"PartyAcctRelStatusCode": "Valid"}}
                for ident, account in sorted(self.accounts.items()) if account["party"] == party]
        if not rows:
            return None
        return {"Status": _status(), "RecCtrlOut": {"SentRecCount": len(rows)}, "PartyAcctRelRec": rows}

    def _account(self, body, key):
        keys = body["AcctSel"]["AcctKeys"]
        account = self.accounts.get(keys["AcctId"])
        if account is None or account["type"] != keys.get("AcctType"):
            return None
        record = {"AcctKeys": {"AcctId": keys["AcctId"], "AcctType": account["type"]},
                  "AcctStatus": {"AcctStatusCode": "Valid"}}
        if key == "dda":
            record["DepositAcctInfo"] = {"AcctBal": [
                {"BalType": "Avail", "CurAmt": _amount(account["avail"])},
                {"BalType": "Ledger", "CurAmt": _amount(account["ledger"])}]}
        else:
            record["LoanAcctInfo"] = {
                "NextPmt": {"PmtCompositeAmt": [
                    {"CompositeCurAmtType": "Total", "CurAmt": _amount(account["next_total"])}],
                    "PmtDt": account["next_date"]},
                "AcctBal": [{"BalType": "PayOffAmt", "CurAmt": _amount(account["payoff"])},
                            {"BalType": "PastDue", "CurAmt": _amount(account["past_due"])},
                            {"BalType": "PmtDue", "CurAmt": _amount(account["pmt_due"])}]}
        return {"Status": _status(), "AcctRec": record}

    def _transactions(self, body):
        selection = body["AcctTrnSel"]
        ident = selection["AcctKeys"]["AcctId"]
        if ident not in TRANSACTIONS or self.accounts[ident]["type"] != "DDA":
            return None
        cursor = body.get("RecCtrlIn", {}).get("Cursor")
        start = int(cursor) if cursor is not None and cursor.isdigit() else 0
        rows = TRANSACTIONS[ident][start:start + PAGE]
        records = [{"AcctTrnKeys": {"AcctKeys": {"AcctId": ident, "AcctType": "DDA"}, "AcctTrnIdent": row[0]},
                    "AcctTrnInfo": {"DrCrType": row[2], "PostedDt": row[1], "TrnAmt": _amount(row[3]),
                                    "Desc": [row[4]]},
                    "AcctTrnStatus": {"AcctTrnStatusCode": "Valid"}} for row in rows]
        out = {"SentRecCount": len(records)}
        if start + PAGE < len(TRANSACTIONS[ident]):
            out["Cursor"] = str(start + PAGE)
        return {"Status": _status(), "RecCtrlOut": out, "AcctTrnRec": records}

    def _transfer(self, body):
        info = body["XferInfo"]
        if info.get("TransferType") != "FundsTransfer" or info.get("IsValidateOnly") is True:
            return 400, None
        source = self.accounts.get(info["FromAcctRef"]["AcctKeys"]["AcctId"])
        target = self.accounts.get(info["ToAcctRef"]["AcctKeys"]["AcctId"])
        amount = round(info["CurAmt"]["Amt"] * 100)
        if (source is None or target is None or source["type"] != "DDA" or target["type"] != "DDA"
                or info["FromAcctRef"]["AcctKeys"].get("AcctType") != "DDA"
                or info["ToAcctRef"]["AcctKeys"].get("AcctType") != "DDA"
                or source["party"] != target["party"] or amount <= 0
                or info["CurAmt"]["CurCode"]["CurCodeValue"] != "USD"
                or info["FromAcctRef"]["AcctKeys"]["AcctId"] == info["ToAcctRef"]["AcctKeys"]["AcctId"]
                or amount > source["avail"]):
            return 422, None
        source["avail"] -= amount
        source["ledger"] -= amount
        target["avail"] += amount
        target["ledger"] += amount
        self.transfers += 1
        return 201, {"Status": _status(), "XferStatusRec": {
            "XferKeys": {"AcctKeys": {"AcctId": info["FromAcctRef"]["AcctKeys"]["AcctId"], "AcctType": "DDA"}},
            "XferStatus": {"XferStatusCode": "Valid"}}}

    # -- wire -------------------------------------------------------------
    def handle(self, path: str, header_value: str | None, raw: bytes):
        """Return (status, body, drop_connection)."""
        route = {self.contract.path(key): key for key in ("party", "trn", "xfer")}
        try:
            if path == self.contract.path("dda"):
                body = json.loads(raw)
                key = self.contract.document_for_account(
                    body.get("AcctSel", {}).get("AcctKeys", {}).get("AcctType"))
            elif path in route:
                key = route[path]
                body = json.loads(raw)
            else:
                return 404, {"Status": _status("404", "Unknown operation", "Error")}, False
            self.contract.validate_header(key, header_value or "")
            self.contract.validate_request(key, body)
        except (ContractError, ValueError, TypeError, AttributeError):
            return 400, {"Status": _status("400", "Invalid request", "Error")}, False
        with self.lock:
            if key in {"dda", "loan"}:
                response, status = self._account(body, key), 200
            elif key == "party":
                response, status = self._party(body), 200
            elif key == "trn":
                response, status = self._transactions(body), 200
            else:
                status, response = self._transfer(body)
                if status == 201 and self.fault == "transfer-response-lost":
                    return 0, None, True
            if response is None:
                # The pinned default schema requires success fields, so an error
                # body cannot satisfy it. Recorded limitation: the mock returns a
                # small Status-only body and the client treats it as unavailable.
                return (404 if status == 200 else status), {
                    "Status": _status("404", "Not found or not permitted", "Error")}, False
            self.contract.validate_response(key, status, response)  # self-check
            return status, response, False


def serve(mock: PremierMock, sock) -> ThreadingHTTPServer:
    """Serve on an already-bound loopback socket; returns the running server."""

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):  # noqa: N802
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(min(length, 65536))
            status, body, drop = mock.handle(self.path, self.headers.get("EFXHeader"), raw)
            if drop:
                self.close_connection = True
                self.connection.close()
                return
            payload = json.dumps(body).encode()
            self.send_response(status)
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
