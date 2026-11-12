# SPDX-License-Identifier: MIT
"""Direct SilverLake jXchange SOAP client for six operations.

Each call builds the vendor request element, validates it against the pinned
schema before sending, sends one SOAP 1.1 envelope with the operation's
SOAPAction, then validates the reply body before reading a field. A SOAP fault
is a refusal, never a value. No retries, no fallback to another field.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from urllib.parse import urlsplit
import xml.etree.ElementTree as ET

import httpx

from .contract import ContractError, SilverLakeContract, SOAP_ENV, envelope, header, open_envelope, q, sub
from .mock import PATH


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
            self.contract.validate(request)
        except ContractError:
            raise Unavailable("invalid_request") from None
        try:
            with httpx.Client(trust_env=False, timeout=self.timeout, follow_redirects=False,
                              transport=self._transport) as http:
                reply = http.post(self.url, content=envelope(request), headers={
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

    @staticmethod
    def _find(element, *path):
        node = element
        for name in path:
            node = node.find(q(name)) if node is not None else None
        return node

    def accounts(self, customer: str) -> list[tuple[str, str]]:
        request = ET.Element(q("AcctSrch"))
        header(request, search=True, max_rec=20)
        sub(request, "CustId", customer)
        body = self._call("AcctSrch", request)
        array = body.find(q("AcctSrchRecArray"))
        records = array.findall(q("AcctSrchRec")) if array is not None else []
        return [(self._find(r, "AccountId", "AcctId").text, self._find(r, "AccountId", "AcctType").text)
                for r in records if self._find(r, "AccountId", "AcctId") is not None]

    def _in_acct(self, request, ident, kind):
        node = sub(request, "InAcctId")
        sub(node, "AcctId", ident)
        sub(node, "AcctType", kind)

    def available_balance(self, ident: str, kind: str) -> str:
        request = ET.Element(q("AcctBalInq"))
        header(request)
        self._in_acct(request, ident, kind)
        node = self._call("AcctBalInq", request).find(q("AvlBal"))
        if node is None or node.text is None:  # never fall back to CurBal
            raise Unavailable("no_available_balance")
        return format(_money(node.text), "f")

    def history(self, ident: str, kind: str, cursor: str | None = None, max_rec: int = 3):
        request = ET.Element(q("AcctHistSrch"))
        header(request, search=True, max_rec=max_rec, cursor=cursor)
        self._in_acct(request, ident, kind)
        body = self._call("AcctHistSrch", request)
        rows = []
        array = body.find(q("AcctHistSrchRecArray"))
        for record in (array.findall(q("AcctHistSrchRec")) if array is not None else []):
            dep = record.find(q("DepHistSrchRec"))
            if dep is None:
                continue
            posted, amount, kind_text = (self._find(dep, "PostDt"), self._find(dep, "Amt"), self._find(dep, "TrnType"))
            if posted is None or amount is None:
                continue  # an absent field is unavailable, never guessed
            rows.append({"date": posted.text[:10], "amount": format(_money(amount.text), "f"),
                         "direction": (kind_text.text or "").lower() if kind_text is not None else "unknown",
                         "currency": "USD"})
        hdr = body.find(q("SrchMsgRsHdr"))
        next_cursor = self._find(hdr, "Cursor")
        return rows, (next_cursor.text if next_cursor is not None else None)

    def loan_payment(self, ident: str):
        """PmtAmtDue and NxtPayDt as two separate facts. Never PmtAmt or past due."""
        request = ET.Element(q("AcctInq"))
        header(request)
        self._in_acct(request, ident, "L")
        info = self._find(self._call("AcctInq", request), "LnAcctInqRec", "x_LnInfoRec", "LnInfoRec")
        due, date = self._find(info, "PmtAmtDue"), self._find(info, "NxtPayDt")
        return {"amount_due": format(_money(due.text), "f") if due is not None and due.text else None,
                "next_due_date": date.text if date is not None and date.text else None,
                "currency": "USD"}

    def payoff(self, ident: str, effective_date: str):
        """A dated quote only when the reply echoes the same date with an amount."""
        request = ET.Element(q("LnPayoffInq"))
        header(request)
        account = sub(request, "AccountId")
        sub(account, "AcctId", ident)
        sub(account, "AcctType", "L")
        sub(request, "EffDt", effective_date)
        body = self._call("LnPayoffInq", request)
        echoed, amount = body.find(q("EffDt")), body.find(q("PayoffAmt"))
        if echoed is None or echoed.text != effective_date or amount is None or not amount.text:
            raise Unavailable("no_quote_for_date")
        return {"as_of": effective_date, "amount": format(_money(amount.text), "f"), "currency": "USD"}

    def transfer(self, source: tuple[str, str], destination: tuple[str, str], amount: Decimal) -> str:
        """One immediate internal XferAdd. Returns accepted or refused; never posted."""
        request = ET.Element(q("XferAdd"))
        header(request)
        sender = sub(request, "AcctIdFrom")
        sub(sender, "FromAcctId", source[0])
        sub(sender, "FromAcctType", source[1])
        receiver = sub(request, "AcctIdTo")
        sub(receiver, "ToAcctId", destination[0])
        sub(receiver, "ToAcctType", destination[1])
        sub(sub(request, "XferRec"), "Amt", format(amount, "f"))
        try:
            self.contract.validate(request)
        except ContractError:
            return "refused"  # never sent
        try:
            body = self._call("XferAdd", request, write=True)
        except Fault as fault:
            if fault.side == "Client" or fault.code in TRANSFER_REFUSALS:
                return "refused"
            raise UnknownOutcome("server_fault") from None
        except Unavailable:
            raise UnknownOutcome("unusable_reply") from None
        status = body.find(q("RsStat"))
        if status is None or (status.text or "").strip() != "Success":
            raise UnknownOutcome("unrecognised_status")
        return "accepted"
