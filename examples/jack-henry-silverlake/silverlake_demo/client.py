# SPDX-License-Identifier: MIT
"""Direct SilverLake jXchange SOAP client for six operations.

Each call builds the vendor request as its generated dataclass (vendor_models,
see vendor_api.py), validates the resulting element against the pinned schema
before sending, sends one SOAP 1.1 envelope with the operation's SOAPAction,
then validates the reply body against the schema and reads it through its
dataclass. A SOAP fault is a refusal, never a value. No retries, no fallback
to another field.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from urllib.parse import urlsplit
import xml.etree.ElementTree as ET

import httpx

from xsdata.models.datatype import XmlDate

from . import vendor_api
from .contract import ContractError, SilverLakeContract, SOAP_ENV, envelope, open_envelope, q
from .mock import PATH
from .vendor_api import ModelError
from .vendor_models import inquiry, transaction


class Unavailable(Exception):
    """A closed reason: bad status, fault, bad body or unreachable."""


class Fault(Unavailable):
    """A SOAP fault: who it blames (Client or Server) and any business error code."""

    def __init__(self, side: str, code: str | None):
        super().__init__("fault")
        self.side, self.code = side, code


# Documented business errors that mean "not done" for a transfer. Anything else
# after a send, including a Server fault, is an unknown outcome, never a refusal.
TRANSFER_REFUSALS = frozenset({"100199", "400001"})


class UnknownOutcome(Exception):
    """A write was sent but no usable reply arrived. Never resend."""


def _money(text) -> Decimal:
    try:
        value = Decimal(text)
    except (InvalidOperation, TypeError):
        raise Unavailable("invalid_amount") from None
    if not value.is_finite():
        raise Unavailable("invalid_amount")
    return value.quantize(Decimal("0.01"))


class SilverLakeClient:
    def __init__(self, contract: SilverLakeContract, base_url: str, *, timeout=5.0, transport=None):
        parts = urlsplit(base_url)
        if (parts.scheme != "http" or parts.hostname != "127.0.0.1" or parts.port is None
                or parts.path not in {"", "/"} or parts.username or parts.password
                or parts.query or parts.fragment):
            raise ValueError("the mock client accepts only an explicit IPv4 loopback origin")
        self.contract, self.url, self.timeout = contract, base_url.rstrip("/") + PATH, timeout
        self._transport = transport  # tests only: an in-process stand-in for the network

    def _call(self, operation: str, request: ET.Element, *, write=False) -> ET.Element:
        try:
            wire = envelope(request)
            # Validate the exact bytes that will be sent, read back the way a server reads them.
            self.contract.validate(open_envelope(wire))
        except ContractError:
            raise Unavailable("invalid_request") from None
        try:
            with httpx.Client(trust_env=False, timeout=self.timeout, follow_redirects=False,
                              transport=self._transport) as http:
                reply = http.post(self.url, content=wire, headers={
                    "Content-Type": "text/xml; charset=utf-8",
                    "SOAPAction": '"%s"' % self.contract.actions[operation]})
        except Exception:
            raise (UnknownOutcome("no_reply") if write else Unavailable("unreachable")) from None
        try:
            body = open_envelope(reply.content)
        except ContractError:
            raise (UnknownOutcome("invalid_reply") if write else Unavailable("invalid_response")) from None
        if body.tag == "{%s}Fault" % SOAP_ENV:
            side = (body.findtext("faultcode") or "").rsplit(":", 1)[-1]
            code = None
            detail = body.find("detail")
            if detail is not None:
                code = detail.findtext(q("ErrCode"))
            raise Fault(side, code)
        if reply.status_code != 200 or body.tag != q(operation + "Response"):
            raise (UnknownOutcome("unexpected_reply") if write else Unavailable("invalid_response"))
        try:
            self.contract.validate(body)
        except ContractError:
            raise (UnknownOutcome("invalid_reply") if write else Unavailable("invalid_response")) from None
        return body

    def _request(self, model) -> ET.Element:
        """The request dataclass as the body element; a model mismatch is never sent."""
        try:
            return vendor_api.to_element(model)
        except ModelError:
            raise Unavailable("invalid_request") from None

    @staticmethod
    def _reply(operation: str, body: ET.Element, *, write=False):
        """The schema-valid reply body as its dataclass (or, for AcctInq, the loan payment record)."""
        try:
            return vendor_api.reply(operation, body)
        except ModelError:
            raise (UnknownOutcome("invalid_reply") if write else Unavailable("invalid_response")) from None

    def accounts(self, customer: str) -> list[tuple[str, str]]:
        request = inquiry.AcctSrch(srch_msg_rq_hdr=_header(inquiry, search=True, max_rec=20),
                                   cust_id=inquiry.CustIdType(value=customer))
        body = self._reply("AcctSrch", self._call("AcctSrch", self._request(request)))
        array = body.acct_srch_rec_array
        records = array.acct_srch_rec if array is not None else []
        return [(_text(r.account_id.acct_id), _text(r.account_id.acct_type))
                for r in records if r.account_id is not None]

    @staticmethod
    def _in_acct(ident, kind):
        return inquiry.AccountIdCtype(acct_id=inquiry.AcctIdType(value=ident),
                                      acct_type=inquiry.AcctTypeType(value=kind))

    def available_balance(self, ident: str, kind: str) -> str:
        request = inquiry.AcctBalInq(msg_rq_hdr=_header(inquiry), in_acct_id=self._in_acct(ident, kind))
        node = self._reply("AcctBalInq", self._call("AcctBalInq", self._request(request))).avl_bal
        if node is None:  # never fall back to CurBal
            raise Unavailable("no_available_balance")
        return format(_money(node.value), "f")

    def history(self, ident: str, kind: str, cursor: str | None = None, max_rec: int = 3):
        request = inquiry.AcctHistSrch(srch_msg_rq_hdr=_header(inquiry, search=True, max_rec=max_rec, cursor=cursor),
                                       in_acct_id=self._in_acct(ident, kind))
        body = self._reply("AcctHistSrch", self._call("AcctHistSrch", self._request(request)))
        rows = []
        array = body.acct_hist_srch_rec_array
        for record in (array.acct_hist_srch_rec if array is not None else []):
            dep = record.dep_hist_srch_rec
            if dep is None:
                continue
            if dep.post_dt is None or dep.amt is None:
                continue  # an absent field is unavailable, never guessed
            rows.append({"date": str(dep.post_dt.value)[:10], "amount": format(_money(dep.amt.value), "f"),
                         "direction": (dep.trn_type.value or "").lower() if dep.trn_type is not None else "unknown",
                         "currency": "USD"})
        next_cursor = body.srch_msg_rs_hdr.cursor
        return rows, (_text(next_cursor) if next_cursor is not None else None)

    def loan_payment(self, ident: str):
        """PmtAmtDue and NxtPayDt as two separate facts. Never PmtAmt or past due."""
        request = inquiry.AcctInq(msg_rq_hdr=_header(inquiry), in_acct_id=self._in_acct(ident, "L"))
        info = self._reply("AcctInq", self._call("AcctInq", self._request(request)))
        due, date = (info.pmt_amt_due, info.nxt_pay_dt) if info is not None else (None, None)
        return {"amount_due": format(_money(due.value), "f") if due is not None else None,
                "next_due_date": str(date.value) if date is not None else None,
                "currency": "USD"}

    def payoff(self, ident: str, effective_date: str):
        """A dated quote only when the reply echoes the same date with an amount."""
        try:
            date = XmlDate.from_string(effective_date)
        except (ValueError, TypeError):
            raise Unavailable("invalid_request") from None
        request = inquiry.LnPayoffInq(msg_rq_hdr=_header(inquiry), account_id=self._in_acct(ident, "L"),
                                      eff_dt=inquiry.EffDtType(value=date))
        body = self._reply("LnPayoffInq", self._call("LnPayoffInq", self._request(request)))
        echoed, amount = body.eff_dt, body.payoff_amt
        if echoed is None or str(echoed.value) != effective_date or amount is None:
            raise Unavailable("no_quote_for_date")
        return {"as_of": effective_date, "amount": format(_money(amount.value), "f"), "currency": "USD"}

    def transfer(self, source: tuple[str, str], destination: tuple[str, str], amount: Decimal) -> str:
        """One immediate internal XferAdd. Returns accepted or refused; never posted."""
        model = transaction.XferAdd(
            msg_rq_hdr=_header(transaction),
            acct_id_from=transaction.AcctIdFromCtype(from_acct_id=transaction.AcctIdType(value=source[0]),
                                                     from_acct_type=transaction.AcctTypeType(value=source[1])),
            acct_id_to=transaction.AcctIdToCtype(to_acct_id=transaction.AcctIdType(value=destination[0]),
                                                 to_acct_type=transaction.AcctTypeType(value=destination[1])),
            xfer_rec=transaction.XferRecCtype(amt=transaction.AmtType(value=amount)))
        try:
            request = vendor_api.to_element(model)
            self.contract.validate(request)
        except (ModelError, ContractError):
            return "refused"  # never sent
        try:
            body = self._call("XferAdd", request, write=True)
        except Fault as fault:
            if fault.side == "Client" or fault.code in TRANSFER_REFUSALS:
                return "refused"
            raise UnknownOutcome("server_fault") from None
        except Unavailable:
            raise UnknownOutcome("unusable_reply") from None
        status = self._reply("XferAdd", body, write=True).rs_stat
        if status is None or (status.value or "").strip() != "Success":
            raise UnknownOutcome("unrecognised_status")
        return "accepted"


def _header(models, search: bool = False, max_rec: int | None = None, cursor: str | None = None):
    """The request header of one generated module (inquiry or transaction)."""
    jx = models.JXchangeHdrCtype(audit_usr_id=models.AuditUsrIdType(value="rasa-demo"),
                                 audit_ws_id=models.AuditWsIdType(value="rasa-demo"))
    if not search:
        return models.MsgRqHdrCtype(j_xchange_hdr=jx)
    return models.SrchMsgRqHdrCtype(j_xchange_hdr=jx, max_rec=models.MaxRecType(value=max_rec or 20),
                                    cursor=models.CursorType(value=cursor) if cursor else None)


def _text(node) -> str | None:
    """A text value as ElementTree reads it: an empty element is None."""
    return node.value or None
