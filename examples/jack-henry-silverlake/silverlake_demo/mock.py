# SPDX-License-Identifier: MIT
"""A local SOAP mock of six SilverLake jXchange operations, with fictional data.

It speaks document/literal SOAP 1.1: one POST endpoint, a SOAPAction header, an
envelope whose body is the jXchange request element. Every request body and
every response body it builds is validated against the learner-supplied pinned
schemas. A mock proves our conversation design and adapter; it never proves
compatibility with a real SilverLake system.
"""
from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Lock, Thread
import uuid
import xml.etree.ElementTree as ET

from .contract import ContractError, SilverLakeContract, envelope, header, open_envelope, q, sub, NS, SOAP_ENV

PATH = "/jxchange"

# Authored fictional data. SilverLake account type codes: D deposit, S savings, L loan.
CUSTOMERS = {"C100001": ["1001001", "1001002", "7001001"], "C200002": ["2001001", "2001002", "8001001"]}
ACCOUNTS = {
    "1001001": {"type": "D", "cust": "C100001", "avail": 125000, "cur": 127500, "desc": "Fictional Checking"},
    "1001002": {"type": "S", "cust": "C100001", "avail": 30000, "cur": 30000, "desc": "Fictional Savings"},
    "7001001": {"type": "L", "cust": "C100001", "due": 24240, "regular": 18240, "past_due": 6000,
                "next_pay": "2026-12-01", "next_sched": "2026-12-15", "desc": "Fictional Auto Loan",
                "payoff": {"2026-11-20": 412055, "2026-12-01": 413390}},
    "2001001": {"type": "D", "cust": "C200002", "avail": 80000, "cur": 80000, "desc": "Fictional Checking"},
    "2001002": {"type": "S", "cust": "C200002", "avail": 5000, "cur": 5000, "desc": "Fictional Savings"},
    "8001001": {"type": "L", "cust": "C200002", "due": 9100, "regular": 9100, "past_due": 0,
                "next_pay": "2026-12-10", "next_sched": "2026-12-10", "desc": "Fictional Loan",
                "payoff": {"2026-11-20": 150000}},
}
HISTORY = {
    "1001001": [("2026-11-04", -4200, "Fictional Market"), ("2026-11-03", 90000, "Fictional Payroll"),
                ("2026-11-01", -1550, "Fictional Pharmacy"), ("2026-10-29", -8000, "Fictional Gas Co"),
                ("2026-10-27", 2500, "Fictional Refund")],
    "1001002": [("2026-10-30", 30000, "Fictional Transfer")],
    "2001001": [("2026-11-02", 80000, "Fictional Payroll")],
    "2001002": [("2026-11-02", 5000, "Fictional Deposit")],
}
# Documented SilverLake business errors used by this mock. Not an exhaustive list.
ERR_ZERO_AMOUNT = "100199"
ERR_NOT_FOUND = "400001"  # fictional mock code for an unknown or unpermitted account


def money(cents: int) -> str:
    return f"{cents / 100:.2f}"


class BusinessError(Exception):
    def __init__(self, code, description):
        super().__init__(code)
        self.code, self.description = code, description


class SilverLakeMock:
    def __init__(self, contract: SilverLakeContract, *, fault: str = "none"):
        if fault not in {"none", "transfer-response-lost"}:
            raise ValueError("unknown fault")
        self.contract, self.fault = contract, fault
        self.accounts = {key: dict(value) for key, value in ACCOUNTS.items()}
        self.lock = Lock()
        self.transfers = 0

    @staticmethod
    def _text(element, *path):
        node = element
        for name in path:
            node = node.find(q(name)) if node is not None else None
        return node.text if node is not None else None

    def _account(self, ident, kinds):
        account = self.accounts.get(ident)
        if account is None or account["type"] not in kinds:
            raise BusinessError(ERR_NOT_FOUND, "Account not found")
        return account

    def acct_srch(self, request):
        customer = self._text(request, "CustId")
        if customer not in CUSTOMERS:
            raise BusinessError(ERR_NOT_FOUND, "Customer not found")
        response = ET.Element(q("AcctSrchResponse"))
        hdr = header(response, search=True, response=True)
        sub(hdr, "SentRec", str(len(CUSTOMERS[customer])))
        sub(hdr, "MoreRec", "false")
        array = sub(response, "AcctSrchRecArray")
        for ident in CUSTOMERS[customer]:
            record = sub(array, "AcctSrchRec")
            account_id = sub(record, "AccountId")
            sub(account_id, "AcctId", ident)
            sub(account_id, "AcctType", self.accounts[ident]["type"])
            sub(record, "CustId", customer)
            sub(record, "ProdDesc", self.accounts[ident]["desc"])
        return response

    def acct_bal_inq(self, request):
        ident = self._text(request, "InAcctId", "AcctId")
        kind = self._text(request, "InAcctId", "AcctType")
        account = self._account(ident, {"D", "S"})
        if kind != account["type"]:
            raise BusinessError(ERR_NOT_FOUND, "Account not found")
        response = ET.Element(q("AcctBalInqResponse"))
        header(response, response=True)
        in_acct = sub(response, "InAcctId")
        sub(in_acct, "AcctId", ident)
        sub(in_acct, "AcctType", kind)
        sub(response, "CurBal", money(account["cur"]))
        sub(response, "AvlBal", money(account["avail"]))
        return response

    def acct_hist_srch(self, request):
        ident = self._text(request, "InAcctId", "AcctId")
        account = self._account(ident, {"D", "S"})
        if self._text(request, "InAcctId", "AcctType") != account["type"]:
            raise BusinessError(ERR_NOT_FOUND, "Account not found")
        max_rec = int(self._text(request, "SrchMsgRqHdr", "MaxRec") or 3)
        cursor = self._text(request, "SrchMsgRqHdr", "Cursor")
        start = int(cursor) if cursor and cursor.isdigit() else 0
        rows = HISTORY.get(ident, [])
        page = rows[start:start + max_rec]
        response = ET.Element(q("AcctHistSrchResponse"))
        hdr = header(response, search=True, response=True)
        sub(hdr, "SentRec", str(len(page)))
        more = start + max_rec < len(rows)
        sub(hdr, "MoreRec", "true" if more else "false")
        if more:
            sub(hdr, "Cursor", str(start + max_rec))
        array = sub(response, "AcctHistSrchRecArray")
        for posted, cents, description in page:
            dep = sub(sub(array, "AcctHistSrchRec"), "DepHistSrchRec")
            account_id = sub(dep, "DepAcctId")
            sub(account_id, "AcctId", ident)
            sub(account_id, "AcctType", account["type"])
            sub(dep, "TrnCodeCode", "100" if cents > 0 else "200")
            sub(dep, "TrnCodeDesc", description)
            sub(dep, "PostDt", posted)
            sub(dep, "Amt", money(abs(cents)))
            sub(dep, "TrnType", "Credit" if cents > 0 else "Debit")
            sub(dep, "AffCode", "0")
        return response

    def acct_inq(self, request):
        ident = self._text(request, "InAcctId", "AcctId")
        account = self._account(ident, {"L"})
        if self._text(request, "InAcctId", "AcctType") != "L":
            raise BusinessError(ERR_NOT_FOUND, "Account not found")
        response = ET.Element(q("AcctInqResponse"))
        header(response, response=True)
        x_info = sub(sub(response, "LnAcctInqRec"), "x_LnInfoRec")
        info = sub(x_info, "LnInfoRec")
        # Order follows the schema sequence: PmtAmtDue, PmtAmt, PastDueAmt, NxtSchedPmtDt, NxtPayDt.
        sub(info, "PmtAmtDue", money(account["due"]))
        sub(info, "PmtAmt", money(account["regular"]))
        sub(info, "PastDueAmt", money(account["past_due"]))
        sub(info, "NxtSchedPmtDt", account["next_sched"])
        sub(info, "NxtPayDt", account["next_pay"])
        loan_id = sub(x_info, "LoanAcctId")
        sub(loan_id, "AcctId", ident)
        sub(loan_id, "AcctType", "L")
        sub(sub(x_info, "PersonName"), "ComName", "Fictional Customer")
        return response

    def ln_payoff_inq(self, request):
        ident = self._text(request, "AccountId", "AcctId")
        account = self._account(ident, {"L"})
        wanted = self._text(request, "EffDt")
        response = ET.Element(q("LnPayoffInqResponse"))
        header(response, response=True)
        account_id = sub(response, "AccountId")
        sub(account_id, "AcctId", ident)
        sub(account_id, "AcctType", "L")
        if wanted:
            sub(response, "EffDt", wanted)
        amount = account["payoff"].get(wanted)
        if amount is not None:  # no quote is calculated for any other date
            sub(response, "PayoffAmt", money(amount))
        return response

    def xfer_add(self, request):
        if request.find(q("ACHXferRec")) is not None or request.find(q("FutXferRec")) is not None:
            raise BusinessError(ERR_NOT_FOUND, "Unsupported transfer mode")
        source_id = self._text(request, "AcctIdFrom", "FromAcctId")
        target_id = self._text(request, "AcctIdTo", "ToAcctId")
        amount_text = self._text(request, "XferRec", "Amt")
        source = self._account(source_id, {"D", "S"})
        target = self._account(target_id, {"D", "S"})
        try:
            cents = round(float(amount_text) * 100)
        except (TypeError, ValueError):
            raise BusinessError(ERR_ZERO_AMOUNT, "Invalid amount") from None
        if cents <= 0:
            raise BusinessError(ERR_ZERO_AMOUNT, "Amount must be greater than zero")
        if (source["cust"] != target["cust"] or source_id == target_id or cents > source["avail"]
                or self._text(request, "AcctIdFrom", "FromAcctType") != source["type"]
                or self._text(request, "AcctIdTo", "ToAcctType") != target["type"]):
            raise BusinessError(ERR_NOT_FOUND, "Transfer not permitted")
        source["avail"] -= cents
        source["cur"] -= cents
        target["avail"] += cents
        target["cur"] += cents
        self.transfers += 1
        response = ET.Element(q("XferAddResponse"))
        header(response, response=True)
        sub(response, "XferKey", uuid.uuid4().hex[:20])
        sub(response, "RsStat", "Success")
        return response

    HANDLERS = {"AcctSrch": "acct_srch", "AcctBalInq": "acct_bal_inq", "AcctHistSrch": "acct_hist_srch",
                "AcctInq": "acct_inq", "LnPayoffInq": "ln_payoff_inq", "XferAdd": "xfer_add"}

    def handle(self, action: str | None, raw: bytes):
        """Return (status, body bytes, drop_connection)."""
        try:
            request = open_envelope(raw)
            name = request.tag.split("}", 1)[1] if request.tag.startswith("{" + NS + "}") else ""
            if name not in self.HANDLERS or (action or "").strip('"') != self.contract.actions[name]:
                raise ContractError("action_mismatch")
            self.contract.validate(request)
        except ContractError:
            return 500, fault("Client", "Invalid request"), False
        with self.lock:
            try:
                response = getattr(self, self.HANDLERS[name])(request)
            except BusinessError as error:
                return 500, fault("Server", error.description, error.code), False
            if name == "XferAdd" and self.fault == "transfer-response-lost":
                return 0, b"", True
            try:
                self.contract.validate(response)  # self-check before sending
            except ContractError:
                return 500, fault("Server", "Mock produced an invalid reply"), False
            return 200, envelope(response), False


def fault(code: str, text: str, err_code: str | None = None) -> bytes:
    env = ET.Element("{%s}Envelope" % SOAP_ENV)
    body = ET.SubElement(env, "{%s}Body" % SOAP_ENV)
    soap_fault = ET.SubElement(body, "{%s}Fault" % SOAP_ENV)
    ET.SubElement(soap_fault, "faultcode").text = "soap:" + code
    ET.SubElement(soap_fault, "faultstring").text = text
    if err_code:
        detail = ET.SubElement(soap_fault, "detail")
        record = ET.SubElement(detail, q("ErrCode"))
        record.text = err_code
    return ET.tostring(env, encoding="utf-8", xml_declaration=True)


def serve(mock: SilverLakeMock, sock) -> ThreadingHTTPServer:
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):  # noqa: N802
            if self.path != PATH:
                self.send_response(404)
                self.end_headers()
                return
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(min(length, 262144))
            status, body, drop = mock.handle(self.headers.get("SOAPAction"), raw)
            if drop:
                self.close_connection = True
                self.connection.close()
                return
            self.send_response(status)
            self.send_header("Content-Type", "text/xml; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler, bind_and_activate=False)
    server.socket.close()
    server.socket = sock
    server.server_address = sock.getsockname()
    Thread(target=server.serve_forever, daemon=True).start()
    return server
