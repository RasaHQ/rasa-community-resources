# SPDX-License-Identifier: MIT
"""A local SOAP mock of six SilverLake jXchange operations, with fictional data.

It speaks document/literal SOAP 1.1: one POST endpoint, a SOAPAction header, an
envelope whose body is the jXchange request element. Every request body and
every response body it builds is validated against the learner-supplied pinned
schemas. A mock proves our conversation design and adapter; it never proves
compatibility with a real SilverLake system.
"""
from __future__ import annotations

from decimal import ROUND_HALF_EVEN, Decimal, InvalidOperation
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Lock, Thread
import uuid
import xml.etree.ElementTree as ET

from xsdata.models.datatype import XmlDate

from . import vendor_api
from .contract import ContractError, SilverLakeContract, envelope, header, open_envelope, q, sub, NS, SOAP_ENV
from .vendor_api import ModelError
from .vendor_models import inquiry

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


def money(cents: int) -> Decimal:
    """Whole cents as an exact Decimal amount (USD 1,250.00 for 125000); never a float."""
    if isinstance(cents, bool) or not isinstance(cents, int):
        raise TypeError("money is whole cents")
    return Decimal(cents).scaleb(-2)


def _account_id(ident: str, kind: str):
    return inquiry.AccountIdCtype(acct_id=inquiry.AcctIdType(value=ident), acct_type=inquiry.AcctTypeType(value=kind))


def _rs_header(*, search: bool = False, sent: int = 0, more: bool = False, cursor: str | None = None):
    """The reply header as its dataclass: MsgRsHdr, or SrchMsgRsHdr for a search."""
    jx = inquiry.JXchangeHdrCtype(audit_usr_id=inquiry.AuditUsrIdType(value="rasa-demo"),
                                  audit_ws_id=inquiry.AuditWsIdType(value="rasa-demo"))
    if not search:
        return inquiry.MsgRsHdrCtype(j_xchange_hdr=jx)
    return inquiry.SrchMsgRsHdrCtype(j_xchange_hdr=jx, sent_rec=inquiry.SentRecType(value=sent),
                                     more_rec=inquiry.MoreRecType(value="true" if more else "false"),
                                     cursor=inquiry.CursorType(value=cursor) if cursor else None)


class BusinessError(Exception):
    def __init__(self, code, description):
        super().__init__(code)
        self.code, self.description = code, description


class SilverLakeMock:
    def __init__(self, contract: SilverLakeContract, *, fault: str = "none", data: dict | None = None):
        """`data` comes from demo_data.generate(seed); None means the reference data above."""
        if fault not in {"none", "transfer-response-lost"}:
            raise ValueError("unknown fault")
        self.contract, self.fault = contract, fault
        if data is None:
            data = {"customers": CUSTOMERS, "accounts": ACCOUNTS, "history": HISTORY}
        self.customers, self.history = data["customers"], data["history"]
        self.accounts = {key: dict(value) for key, value in data["accounts"].items()}
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
        if customer not in self.customers:
            raise BusinessError(ERR_NOT_FOUND, "Customer not found")
        response = ET.Element(q("AcctSrchResponse"))
        hdr = header(response, search=True, response=True)
        sub(hdr, "SentRec", str(len(self.customers[customer])))
        sub(hdr, "MoreRec", "false")
        array = sub(response, "AcctSrchRecArray")
        for ident in self.customers[customer]:
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
        return vendor_api.reply_element(inquiry.AcctBalInqResponse(
            msg_rs_hdr=_rs_header(), in_acct_id=_account_id(ident, kind),
            cur_bal=inquiry.CurBalType(value=money(account["cur"])),
            avl_bal=inquiry.AvlBalType(value=money(account["avail"]))))

    def acct_hist_srch(self, request):
        ident = self._text(request, "InAcctId", "AcctId")
        account = self._account(ident, {"D", "S"})
        if self._text(request, "InAcctId", "AcctType") != account["type"]:
            raise BusinessError(ERR_NOT_FOUND, "Account not found")
        max_rec = int(self._text(request, "SrchMsgRqHdr", "MaxRec") or 3)
        cursor = self._text(request, "SrchMsgRqHdr", "Cursor")
        start = int(cursor) if cursor and cursor.isdigit() else 0
        rows = self.history.get(ident, [])
        page = rows[start:start + max_rec]
        more = start + max_rec < len(rows)
        records = [inquiry.AcctHistSrchRecCtype(dep_hist_srch_rec=inquiry.DepHistSrchRecCtype(
            dep_acct_id=_account_id(ident, account["type"]),
            trn_code_code=inquiry.TrnCodeCodeType(value="100" if cents > 0 else "200"),
            trn_code_desc=inquiry.TrnCodeDescType(value=description),
            post_dt=inquiry.PostDtType(value=XmlDate.from_string(posted)),
            amt=inquiry.AmtType(value=money(abs(cents))),
            trn_type=inquiry.TrnTypeType(value="Credit" if cents > 0 else "Debit"),
            aff_code=inquiry.AffCodeType(value="0"))) for posted, cents, description in page]
        return vendor_api.reply_element(inquiry.AcctHistSrchResponse(
            srch_msg_rs_hdr=_rs_header(search=True, sent=len(page), more=more,
                                       cursor=str(start + max_rec) if more else None),
            acct_hist_srch_rec_array=inquiry.AcctHistSrchRecArrayAtype(acct_hist_srch_rec=records)))

    def acct_inq(self, request):
        ident = self._text(request, "InAcctId", "AcctId")
        account = self._account(ident, {"L"})
        if self._text(request, "InAcctId", "AcctType") != "L":
            raise BusinessError(ERR_NOT_FOUND, "Account not found")
        response = ET.Element(q("AcctInqResponse"))
        header(response, response=True)
        x_info = sub(sub(response, "LnAcctInqRec"), "x_LnInfoRec")
        # AcctInqResponse has no generated class; its loan payment record does (vendor_api.LOAN_PAYMENT).
        x_info.append(vendor_api.reply_element(vendor_api.LOAN_PAYMENT(
            pmt_amt_due=inquiry.PmtAmtDueType(value=money(account["due"])),
            pmt_amt=inquiry.PmtAmtType(value=money(account["regular"])),
            past_due_amt=inquiry.PastDueAmtType(value=money(account["past_due"])),
            nxt_sched_pmt_dt=inquiry.NxtSchedPmtDtType(value=XmlDate.from_string(account["next_sched"])),
            nxt_pay_dt=inquiry.NxtPayDtType(value=XmlDate.from_string(account["next_pay"]))),
            vendor_api.LOAN_PAYMENT_PATH[-1]))
        loan_id = sub(x_info, "LoanAcctId")
        sub(loan_id, "AcctId", ident)
        sub(loan_id, "AcctType", "L")
        sub(sub(x_info, "PersonName"), "ComName", "Fictional Customer")
        return response

    def ln_payoff_inq(self, request):
        ident = self._text(request, "AccountId", "AcctId")
        account = self._account(ident, {"L"})
        wanted = self._text(request, "EffDt")
        amount = account["payoff"].get(wanted)  # no quote is calculated for any other date
        return vendor_api.reply_element(inquiry.LnPayoffInqResponse(
            msg_rs_hdr=_rs_header(), account_id=_account_id(ident, "L"),
            eff_dt=inquiry.EffDtType(value=XmlDate.from_string(wanted)) if wanted else None,
            payoff_amt=inquiry.PayoffAmtType(value=money(amount)) if amount is not None else None))

    def xfer_add(self, request):
        if request.find(q("ACHXferRec")) is not None or request.find(q("FutXferRec")) is not None:
            raise BusinessError(ERR_NOT_FOUND, "Unsupported transfer mode")
        source_id = self._text(request, "AcctIdFrom", "FromAcctId")
        target_id = self._text(request, "AcctIdTo", "ToAcctId")
        amount_text = self._text(request, "XferRec", "Amt")
        source = self._account(source_id, {"D", "S"})
        target = self._account(target_id, {"D", "S"})
        try:
            cents = int((Decimal(amount_text) * 100).to_integral_value(ROUND_HALF_EVEN))  # exact, never a float
        except (TypeError, ValueError, InvalidOperation, OverflowError):
            raise BusinessError(ERR_ZERO_AMOUNT, "Invalid amount") from None
        if cents <= 0:
            raise BusinessError(ERR_ZERO_AMOUNT, "Amount must be greater than zero")
        if (source["cust"] != target["cust"] or source_id == target_id or cents > source["avail"]
                or self._text(request, "AcctIdFrom", "FromAcctType") != source["type"]
                or self._text(request, "AcctIdTo", "ToAcctType") != target["type"]):
            raise BusinessError(ERR_NOT_FOUND, "Transfer not permitted")
        response = ET.Element(q("XferAddResponse"))
        header(response, response=True)
        sub(response, "XferKey", uuid.uuid4().hex[:20])
        sub(response, "RsStat", "Success")
        self.contract.validate(response)  # validate BEFORE moving any money
        source["avail"] -= cents
        source["cur"] -= cents
        target["avail"] += cents
        target["cur"] += cents
        self.transfers += 1
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
            except (ContractError, ModelError):
                return 500, fault("Server", "Mock produced an invalid reply"), False
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
