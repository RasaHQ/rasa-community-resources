# SPDX-License-Identifier: MIT
"""Direct client for four generic Banking Hub release operations.

Each call builds the vendor request, validates it against the pinned contract
before sending, then validates the reply before reading a field. Read success is
decided from the EFX status, as Fiserv's response-codes page documents it:
StatusCode 0 with Severity Info. A schema-valid reply is not success on its own,
because every release reply requires only a Status. No retries, no fallback to
another field.

Two selectors come from Fiserv's official Premier sample collection (R2026.3.3),
not from a code list in this release, which declares none: the available
balance is the one AcctBal entry whose BalType is exactly "Avail", and the next
payment amount is the one NextPmt.PmtCompositeAmt entry whose
CompositeCurAmtType is exactly "Total". A missing or repeated entry is
unavailable, never a guess, a first entry or a sum.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
import json
import math
from urllib.parse import urlsplit
from uuid import uuid4

import httpx

from .contract import SUCCESS, ContractError, BankingHubContract

ACCOUNT_TYPES = frozenset({"DDA", "SDA", "LOAN"})  # declared in the same release


class Unavailable(Exception):
    """A closed reason: bad status, bad body or unreachable, never vendor text."""


class NoRecords(Unavailable):
    """EFX 1120 (Info): nothing matches. Not an error, not a value."""


class UnknownOutcome(Exception):
    """A transfer was sent but no usable reply arrived. Never resend."""


def _efx(data) -> tuple[str, str]:
    block = data.get("Status") if isinstance(data, dict) else None
    if not isinstance(block, dict):
        raise Unavailable("no_status")
    # The release declares StatusCode as a string; Fiserv's examples print a number.
    return str(block.get("StatusCode")), str(block.get("Severity"))


def _money(node) -> Decimal:
    if not isinstance(node, dict) or not isinstance(node.get("CurCode"), dict):
        raise Unavailable("no_amount")
    if node["CurCode"].get("CurCodeValue") != "USD":
        raise Unavailable("currency")
    raw = node.get("Amt")
    if isinstance(raw, bool) or not isinstance(raw, (int, float)) or not math.isfinite(raw):
        raise Unavailable("no_amount")
    try:
        return Decimal(str(raw)).quantize(Decimal("0.01"))
    except InvalidOperation:
        raise Unavailable("no_amount") from None


def _exactly_one(entries, field, label):
    if not isinstance(entries, list):
        raise Unavailable("no_" + label.lower())
    found = [entry for entry in entries if isinstance(entry, dict) and entry.get(field) == label]
    if len(found) != 1:  # missing or repeated: unavailable, never the first one
        raise Unavailable("no_" + label.lower())
    return found[0]


class BankingHubClient:
    def __init__(self, contract: BankingHubContract, base_url: str, organization_id: str, *, timeout=5.0):
        parts = urlsplit(base_url)
        if (parts.scheme != "http" or parts.hostname != "127.0.0.1" or parts.port is None
                or parts.path not in {"", "/"} or parts.username or parts.password
                or parts.query or parts.fragment):
            raise ValueError("the mock client accepts only an explicit IPv4 loopback origin")
        self.contract, self.base, self.organization, self.timeout = (
            contract, base_url.rstrip("/"), organization_id, timeout)

    def _post(self, key: str, body: dict, *, write=False) -> dict:
        try:
            self.contract.validate_request(key, body)
        except ContractError:
            raise Unavailable("invalid_request") from None
        header = json.dumps({"OrganizationId": self.organization, "TrnId": str(uuid4()),
                             "Context": {"ClientAppName": "rasa-community-fiserv-banking-hub",
                                         "Channel": "VOICE"}})
        try:
            self.contract.validate_header(key, header)
        except ContractError:
            raise Unavailable("invalid_header") from None
        try:
            with httpx.Client(trust_env=False, timeout=self.timeout, follow_redirects=False) as http:
                reply = http.post(self.base + self.contract.path(key), content=json.dumps(body),
                                  headers={"EFXHeader": header, "Content-Type": "application/json"})
        except Exception:
            # A write may have reached the bank before the connection failed.
            raise (UnknownOutcome("no_reply") if write else Unavailable("unreachable")) from None
        if write and reply.status_code != SUCCESS[key]:
            # Only a 4xx is a clean refusal. Any other status, including another
            # 2xx such as the 200 in Fiserv's older sample, may mean money moved.
            if 400 <= reply.status_code < 500:
                raise Unavailable("status_" + str(reply.status_code))
            raise UnknownOutcome("unexpected_status")
        try:
            data = reply.json()
        except ValueError:
            raise (UnknownOutcome("invalid_reply") if write else Unavailable("invalid_response")) from None
        try:
            self.contract.validate_response(key, reply.status_code, data)
        except ContractError:
            raise (UnknownOutcome("invalid_reply") if write else Unavailable("invalid_response")) from None
        code, severity = _efx(data)
        if not write and reply.status_code == 200 and code == "1120" and severity == "Info":
            raise NoRecords("no_records")
        if reply.status_code != SUCCESS[key] or code != "0" or severity != "Info":
            if write:
                raise UnknownOutcome("not_success")  # sent; the effect is not known
            raise Unavailable("not_success")  # warnings and errors are never success
        return data

    def party_accounts(self, party_id: str) -> list[tuple[str, str]]:
        try:
            data = self._post("party", {"PartyAcctRelSel": {"PartyKeys": {"PartyId": party_id}},
                                        "RecCtrlIn": {"MaxRecLimit": 20}})
        except NoRecords:
            return []
        rows = data.get("PartyAcctRelRec")
        if not isinstance(rows, list) or not rows:
            raise Unavailable("no_relationship_record")  # Status alone is not an empty list
        related = []
        for row in rows:
            keys = row["PartyAcctRelKeys"].get("AcctKeys", {})
            if (row["PartyAcctRelStatus"]["PartyAcctRelStatusCode"] == "Valid"
                    and keys.get("AcctType") in ACCOUNT_TYPES and isinstance(keys.get("AcctId"), str)):
                related.append((keys["AcctId"], keys["AcctType"]))
        return related

    def _record(self, account_id: str, account_type: str) -> dict:
        data = self._post("acct", {"AcctSel": {"AcctKeys": {"AcctId": account_id, "AcctType": account_type}}})
        record = data.get("AcctRec")
        if (not isinstance(record, dict) or record["AcctKeys"].get("AcctId") != account_id
                or record["AcctKeys"].get("AcctType") != account_type):
            raise Unavailable("no_matching_account")  # never read a cross-type record
        return record

    def available_balance(self, account_id: str) -> Decimal:
        """The one DepositAcctInfo.AcctBal entry with BalType exactly "Avail"."""
        balances = self._record(account_id, "DDA").get("DepositAcctInfo", {}).get("AcctBal")
        return _money(_exactly_one(balances, "BalType", "Avail").get("CurAmt"))

    def loan_payment(self, account_id: str) -> dict:
        """NextPmt PmtDt and the one PmtCompositeAmt entry typed exactly "Total"."""
        next_payment = self._record(account_id, "LOAN").get("LoanAcctInfo", {}).get("NextPmt", {})
        date = next_payment.get("PmtDt") if isinstance(next_payment, dict) else None
        if not isinstance(date, str) or not date:
            raise Unavailable("no_next_payment_date")
        total = _exactly_one(next_payment.get("PmtCompositeAmt"), "CompositeCurAmtType", "Total")
        return {"due_date": date, "amount": format(_money(total.get("CurAmt")), "f"), "currency": "USD"}

    def transfer(self, source_id: str, source_type: str, destination_id: str, destination_type: str,
                 amount: Decimal) -> str:
        """One immediate own-account transfer. Returns accepted or refused, never posted.

        XferInfo.TransferType is optional in this release and has no declared
        values. Fiserv's official Premier Add Transfer samples omit it, so this
        request omits it too, and carries no recurrence fields.
        """
        body = {"XferInfo": {
            "FromAcctRef": {"AcctKeys": {"AcctId": source_id, "AcctType": source_type}},
            "ToAcctRef": {"AcctKeys": {"AcctId": destination_id, "AcctType": destination_type}},
            "CurAmt": {"Amt": float(amount), "CurCode": {"CurCodeType": "ISO4217-Alpha",
                                                          "CurCodeValue": "USD"}}}}
        try:
            data = self._post("xfer", body, write=True)
        except Unavailable:
            # For a write, Unavailable means the request was never sent (invalid
            # request or header) or the vendor answered 4xx: a clean refusal.
            return "refused"
        status = data.get("XferStatusRec", {}).get("XferStatus", {}).get("XferStatusCode")
        if status == "Valid":
            return "accepted"  # Valid is not proof of final posting
        if status == "Rejected":
            return "refused"
        raise UnknownOutcome("unrecognised_status")
