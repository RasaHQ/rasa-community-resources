# SPDX-License-Identifier: MIT
"""Direct Banking Hub (Premier) client for the five selected operations.

Each call builds the vendor request, validates it against the pinned contract
before sending, then validates the response before reading a field. No retries,
no refresh, no fallback to another balance or payoff field.
"""
from __future__ import annotations

from decimal import Decimal
import json
from urllib.parse import urlsplit
from uuid import uuid4

import httpx

from .contract import ContractError, PremierContract


class Unavailable(Exception):
    """A closed reason: bad status, bad body or unreachable, never vendor text."""


class NoRecords(Unavailable):
    """The service answered that nothing matches. Not an error, not a value."""


class UnknownOutcome(Exception):
    """A write was sent but no usable reply arrived. Never resend."""


def _money(node) -> Decimal:
    value = Decimal(str(node["Amt"]))
    if node["CurCode"]["CurCodeValue"] != "USD":
        raise Unavailable("currency")
    return value.quantize(Decimal("0.01"))


class PremierClient:
    def __init__(self, contract: PremierContract, base_url: str, organization_id: str, *, timeout=5.0):
        parts = urlsplit(base_url)
        if (parts.scheme != "http" or parts.hostname != "127.0.0.1" or parts.port is None
                or parts.path not in {"", "/"} or parts.username or parts.password
                or parts.query or parts.fragment):
            raise ValueError("the mock client accepts only an explicit IPv4 loopback origin")
        self.contract, self.base, self.organization, self.timeout = (
            contract, base_url.rstrip("/"), organization_id, timeout)

    def _send(self, key: str, header: str, body: dict):
        """One HTTP POST. Returns (status, parsed JSON or None). Subclasses add auth."""
        with httpx.Client(trust_env=False, timeout=self.timeout, follow_redirects=False) as http:
            reply = http.post(self.base + self.contract.path(key), content=json.dumps(body),
                              headers={"EFXHeader": header, "Content-Type": "application/json"})
        try:
            return reply.status_code, reply.json()
        except ValueError:
            return reply.status_code, None

    def _post(self, key: str, body: dict, *, write=False):
        try:
            self.contract.validate_request(key, body)
        except ContractError:
            raise Unavailable("invalid_request") from None
        header = json.dumps({"OrganizationId": self.organization, "TrnId": str(uuid4()),
                             "Context": {"ClientAppName": "rasa-community-fiserv-premier",
                                         "Channel": "VOICE"}})
        try:
            self.contract.validate_header(key, header)
        except ContractError:
            raise Unavailable("invalid_header") from None
        try:
            status, data = self._send(key, header, body)
        except Unavailable:
            raise  # refused before sending (for example by the quota ledger)
        except Exception:
            raise (UnknownOutcome("no_reply") if write else Unavailable("unreachable")) from None
        expected = {"xfer": 201}.get(key, 200)
        if status != expected:
            if write and status >= 500:
                raise UnknownOutcome("server_error")
            raise Unavailable("status_" + str(status))
        try:
            self.contract.validate_response(key, status, data)
        except ContractError:
            if write:
                raise UnknownOutcome("invalid_reply") from None
            # Observed on the Premier trial: "no records" arrives as HTTP 200 with
            # only a Status block (StatusCode 1120, Severity Info), which the pinned
            # schema does not allow. Treat a Status-only Info/Warning body as none.
            if (isinstance(data, dict) and set(data) == {"Status"} and isinstance(data["Status"], dict)
                    and data["Status"].get("Severity") in {"Info", "Warning"}):
                raise NoRecords("no_records") from None
            raise Unavailable("invalid_response") from None
        return data

    def party_accounts(self, party_id: str) -> list[tuple[str, str]]:
        try:
            data = self._post("party", {"PartyAcctRelSel": {"PartyKeys": {"PartyId": party_id}},
                                        "RecCtrlIn": {"MaxRecLimit": 20}})
        except NoRecords:
            return []
        return [(row["PartyAcctRelKeys"]["AcctKeys"]["AcctId"],
                 row["PartyAcctRelKeys"]["AcctKeys"]["AcctType"]) for row in data["PartyAcctRelRec"]]

    def available_balance(self, account_id: str) -> Decimal:
        data = self._post("dda", {"AcctSel": {"AcctKeys": {"AcctId": account_id, "AcctType": "DDA"}}})
        for entry in data["AcctRec"].get("DepositAcctInfo", {}).get("AcctBal", []):
            if entry["BalType"] == "Avail":  # no ledger, current or memo fallback
                return _money(entry["CurAmt"])
        raise Unavailable("no_available_balance")

    def transactions(self, account_id: str, cursor: str | None = None):
        body = {"AcctTrnSel": {"AcctKeys": {"AcctId": account_id, "AcctType": "DDA"},
                               "TrnPostType": "ExcludeMemoPost"}}
        if cursor:
            body["RecCtrlIn"] = {"Cursor": cursor}
        data = self._post("trn", body)
        rows = []
        for record in data["AcctTrnRec"]:
            info = record["AcctTrnInfo"]
            if "PostedDt" not in info or "TrnAmt" not in info or "DrCrType" not in info:
                continue  # an absent field is unavailable, never guessed
            rows.append({"date": info["PostedDt"][:10], "direction": info["DrCrType"].lower(),
                         "amount": format(_money(info["TrnAmt"]), "f"), "currency": "USD"})
        return rows, data["RecCtrlOut"].get("Cursor")

    def _loan(self, account_id: str) -> dict:
        data = self._post("loan", {"AcctSel": {"AcctKeys": {"AcctId": account_id, "AcctType": "LOAN"}}})
        return data["AcctRec"].get("LoanAcctInfo", {})

    def loan_payment(self, account_id: str):
        """NextPmt Total and PmtDt only; never sum parts or use due/past-due."""
        next_payment = self._loan(account_id).get("NextPmt", {})
        total = [part for part in next_payment.get("PmtCompositeAmt", [])
                 if part.get("CompositeCurAmtType") == "Total"]
        if len(total) != 1 or "PmtDt" not in next_payment:
            raise Unavailable("no_next_payment")
        return {"due_date": next_payment["PmtDt"], "amount": format(_money(total[0]["CurAmt"]), "f"),
                "currency": "USD"}

    def current_payoff(self, account_id: str):
        """Current PayOffAmt only; a dated quote is a different operation."""
        for entry in self._loan(account_id).get("AcctBal", []):
            if entry["BalType"] == "PayOffAmt":
                return {"amount": format(_money(entry["CurAmt"]), "f"), "currency": "USD"}
        raise Unavailable("no_payoff")

    def transfer(self, source_id: str, destination_id: str, amount: Decimal) -> str:
        """One immediate own-account FundsTransfer. Returns accepted, never posted."""
        body = {"XferInfo": {
            "TransferType": "FundsTransfer",
            "FromAcctRef": {"AcctKeys": {"AcctId": source_id, "AcctType": "DDA"}},
            "ToAcctRef": {"AcctKeys": {"AcctId": destination_id, "AcctType": "DDA"}},
            "CurAmt": {"Amt": float(amount), "CurCode": {"CurCodeType": "ISO4217-Alpha",
                                                          "CurCodeValue": "USD"}}}}
        try:
            data = self._post("xfer", body, write=True)
        except Unavailable:
            # For a write, Unavailable means the request was never sent (invalid
            # request or header) or the vendor answered 4xx: a clean refusal.
            return "refused"
        if data["XferStatusRec"]["XferStatus"]["XferStatusCode"] != "Valid":
            raise UnknownOutcome("unrecognised_status")
        return "accepted"  # Valid is not proof of final posting
