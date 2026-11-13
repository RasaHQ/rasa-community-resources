# SPDX-License-Identifier: MIT
"""Optional MANUAL check against the Fiserv Banking Hub (Premier) trial. Never automatic.

Normal start-up, tests and CI always use the local mock, even when the trial
secrets are present. This command runs only when a person types it. It reads
the three secrets from the environment only, never prints them, gets one token
with HTTP Basic authentication, and makes at most three core calls, each one
charged to the local quota ledger BEFORE it is sent. It reads; it never moves
money. A trial is not production and does not certify anything.

Usage, inside a Codespace terminal in the example folder:
  python -m premier_demo.trial import-budget var/private/manual-trial-budget.json --runner <id>
  python -m premier_demo.trial read --runner <id> --trial <id> --period <id> --party <party id>
  python -m premier_demo.trial read ... --checking <account id> --loan <account id>
"""
from __future__ import annotations

import argparse
import base64
import os
from pathlib import Path
import sys
from uuid import uuid4

import httpx

from .client import NoRecords, PremierClient, Unavailable, UnknownOutcome
from .contract import ContractError, PremierContract
from .quota import ORGANIZATION, Ledger, QuotaRefused

CORE_BASE = "https://bankinghub-cert.fiservapis.com/banking/efx/v1"
TOKEN_URL = "https://bankinghub-cert.fiservapis.com/fts-apim/oauth2/v2"
SECRETS = ("FISERV_BH_API_KEY_NAME", "FISERV_BH_API_KEY", "FISERV_BH_API_SECRET")
LEDGER = Path(__file__).resolve().parents[1] / "var" / "private" / "trial-quota.sqlite3"


class TrialUnavailable(Exception):
    """A closed reason. Never carries a secret, a token or a raw vendor body."""


def credentials(environ=os.environ):
    values = [environ.get(name, "").strip() for name in SECRETS]
    if not all(values):
        # Missing or partial: stay with the mock. Name no variable and no value.
        raise TrialUnavailable("trial_secrets_not_all_present")
    return values[1], values[2]


def fetch_token(key: str, secret: str, ledger: Ledger, run_id: str, *, transport=None) -> str:
    """One token attempt per run, no refresh, charged before it is sent."""
    ledger.charge_token_attempt(run_id)
    basic = base64.b64encode(f"{key}:{secret}".encode()).decode()
    try:
        with httpx.Client(trust_env=False, timeout=15, follow_redirects=False, transport=transport) as http:
            reply = http.post(TOKEN_URL, data={"grant_type": "client_credentials"},
                              headers={"Authorization": "Basic " + basic})
        token = reply.json().get("access_token") if reply.status_code == 200 else None
    except Exception:
        raise TrialUnavailable("token_unreachable") from None
    if not isinstance(token, str) or not token:
        raise TrialUnavailable("token_refused_status_" + str(reply.status_code))
    return token


class TrialClient(PremierClient):
    """The same validated requests as the mock client, sent to the trial host."""

    def __init__(self, contract: PremierContract, token: str, ledger: Ledger, reservation: int,
                 *, transport=None, timeout=15.0, sleep=None):
        import time
        self.contract, self.base, self.organization, self.timeout = contract, CORE_BASE, ORGANIZATION, timeout
        self._token, self._ledger, self._reservation, self._transport = token, ledger, reservation, transport
        self._sleep = sleep or time.sleep

    def _send(self, key, header, wire):
        # Wait for the spacing rule instead of failing every read after the first.
        wait = self._ledger.seconds_until_core()
        if 0 < wait <= 7.0:
            self._sleep(wait)
        try:
            self._ledger.charge_core_attempt(self._reservation)  # BEFORE the physical call
        except QuotaRefused as refused:
            raise Unavailable("quota_" + str(refused)) from None
        from decimal import Decimal
        import json
        with httpx.Client(trust_env=False, timeout=self.timeout, follow_redirects=False,
                          transport=self._transport) as http:
            reply = http.post(self.base + self.contract.path(key), content=wire,
                              headers={"EFXHeader": header, "Content-Type": "application/json",
                                       "Authorization": "Bearer " + self._token})
        try:
            return reply.status_code, json.loads(reply.content, parse_float=Decimal)  # never a float
        except ValueError:
            return reply.status_code, None

    def transfer(self, *args, **kwargs):  # noqa: D102
        raise TrialUnavailable("trial_is_read_only")


def run_reads(client: PremierClient, party: str | None, checking: str | None, loan: str | None):
    """Return printable, non-sensitive lines: counts and outcomes, not raw bodies."""
    lines = []
    if party:
        try:
            accounts = client.party_accounts(party)
            lines.append(f"accounts by party: {len(accounts)} returned "
                         + ", ".join(sorted({kind for _, kind in accounts})))
        except NoRecords:
            lines.append("accounts by party: no records match")
        except Unavailable as exc:
            lines.append(f"accounts by party: unavailable ({exc})")
    if checking:
        try:
            lines.append(f"checking available balance: supplied {client.available_balance(checking)} USD")
        except Unavailable as exc:
            lines.append(f"checking available balance: unavailable ({exc})")
    if loan:
        try:
            payment = client.loan_payment(loan)
            lines.append(f"loan next payment: supplied, due {payment['due_date']}")
        except Unavailable as exc:
            lines.append(f"loan next payment: unavailable ({exc})")
    return lines


def main(argv=None, environ=os.environ):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    budget = sub.add_parser("import-budget", help="Import the operator-written budget attestation")
    budget.add_argument("file", type=Path)
    budget.add_argument("--runner", required=True)
    read = sub.add_parser("read", help="Read-only calls against the trial (at most three)")
    for name in ("runner", "trial", "period"):
        read.add_argument("--" + name, required=True)
    read.add_argument("--party")
    read.add_argument("--checking")
    read.add_argument("--loan")
    args = parser.parse_args(argv)
    try:
        ledger = Ledger(Path(environ.get("PREMIER_TRIAL_LEDGER") or LEDGER))
    except QuotaRefused as refused:
        print("Not run: " + str(refused))
        return 2
    try:
        if args.command == "import-budget":
            result = ledger.import_budget(args.file.read_bytes(), approved_runner=args.runner)
            print(f"Budget imported: remaining {result['remaining']}, held {result['held']}"
                  + (", BLOCKED until resolved" if result["blocked"] else ""))
            return 0
        calls = sum(1 for value in (args.party, args.checking, args.loan) if value)  # one call each
        if calls == 0:
            parser.error("name at least one of --party, --checking, --loan")
        key, secret = credentials(environ)
        contract = PremierContract.from_path()
        binding = (args.trial, args.period, ORGANIZATION, args.runner)
        run_id = uuid4().hex
        reservation = ledger.reserve(run_id, binding, calls)
        try:
            token = fetch_token(key, secret, ledger, run_id)
            client = TrialClient(contract, token, ledger, reservation)
            print("Manual Premier TRIAL check (read only). Not production; not certification.")
            for line in run_reads(client, args.party, args.checking, args.loan):
                print("  " + line)
        finally:
            # Return attempts this run did not use, so the binding is not blocked for good.
            ledger.release_unused(reservation, "end of manual trial run")
        print(f"Ledger now: {ledger.snapshot(binding)}")
        return 0
    except (QuotaRefused, TrialUnavailable, ContractError) as refused:
        print("Not run: " + str(refused).split("\n")[0])
        return 2
    except UnknownOutcome:
        print("Not run: unknown outcome")
        return 2
    finally:
        ledger.close()


if __name__ == "__main__":
    sys.exit(main())
