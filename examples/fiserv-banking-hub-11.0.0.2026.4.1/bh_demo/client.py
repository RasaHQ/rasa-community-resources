# SPDX-License-Identifier: MIT
"""Direct client for two generic Banking Hub release operations.

Each call builds the vendor request, validates it against the pinned contract
before sending, then validates the reply before reading a field. Success is
decided from the EFX status, as Fiserv's response-codes page documents it:
StatusCode 0 with Severity Info. A schema-valid reply is not success on its own,
because every release reply requires only a Status. No retries, no fallback to
another field.
"""
from __future__ import annotations

import json
from urllib.parse import urlsplit
from uuid import uuid4

import httpx

from .contract import ContractError, BankingHubContract

ACCOUNT_TYPES = frozenset({"DDA", "SDA", "LOAN"})  # declared in the same release


class Unavailable(Exception):
    """A closed reason: bad status, bad body or unreachable, never vendor text."""


class NoRecords(Unavailable):
    """EFX 1120 (Info): nothing matches. Not an error, not a value."""


def _efx(data) -> tuple[str, str]:
    block = data.get("Status") if isinstance(data, dict) else None
    if not isinstance(block, dict):
        raise Unavailable("no_status")
    # The release declares StatusCode as a string; Fiserv's examples print a number.
    return str(block.get("StatusCode")), str(block.get("Severity"))


class BankingHubClient:
    def __init__(self, contract: BankingHubContract, base_url: str, organization_id: str, *, timeout=5.0):
        parts = urlsplit(base_url)
        if (parts.scheme != "http" or parts.hostname != "127.0.0.1" or parts.port is None
                or parts.path not in {"", "/"} or parts.username or parts.password
                or parts.query or parts.fragment):
            raise ValueError("the mock client accepts only an explicit IPv4 loopback origin")
        self.contract, self.base, self.organization, self.timeout = (
            contract, base_url.rstrip("/"), organization_id, timeout)

    def _post(self, key: str, body: dict) -> dict:
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
            data = reply.json()
        except Exception:
            raise Unavailable("unreachable") from None
        try:
            self.contract.validate_response(key, reply.status_code, data)
        except ContractError:
            raise Unavailable("invalid_response") from None
        code, severity = _efx(data)
        if reply.status_code == 200 and code == "1120" and severity == "Info":
            raise NoRecords("no_records")
        if reply.status_code != 200 or code != "0" or severity != "Info":
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

    def next_payment_date(self, account_id: str) -> str:
        """LoanAcctInfo.NextPmt.PmtDt only. The amount needs an unsourced code."""
        data = self._post("acct", {"AcctSel": {"AcctKeys": {"AcctId": account_id, "AcctType": "LOAN"}}})
        record = data.get("AcctRec")
        if (not isinstance(record, dict) or record["AcctKeys"].get("AcctId") != account_id
                or record["AcctKeys"].get("AcctType") != "LOAN"):
            raise Unavailable("no_matching_account")  # never read a cross-type record
        date = record.get("LoanAcctInfo", {}).get("NextPmt", {}).get("PmtDt")
        if not isinstance(date, str) or not date:
            raise Unavailable("no_next_payment_date")
        return date
