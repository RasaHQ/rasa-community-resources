# SPDX-License-Identifier: MIT
"""Seeded fictional demo data for the local mock.

Seed 0 is the reference data in ``fixtures/fictional.json``: the README's
checked sequence, the tests and the recorded exchanges use it. Any other seed
draws different, plausible fictional amounts, dates and transactions from
``random.Random(seed)`` only, in exactly the same structure, with the same
account number, ids, aliases and currency. No real company or person names.

Every amount is a normal draw clipped to a sensible range and rounded to whole
cents at once, then turned into an exact Decimal; no amount is ever a float.
Rates and shares are drawn as whole numbers (basis points, percent).
"""
from __future__ import annotations

from copy import deepcopy
from datetime import date, timedelta
from decimal import ROUND_FLOOR, Decimal
import hashlib
import json
from pathlib import Path
import random

REFERENCE_SEED = 0
MAX_SEED = 999_999
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "fictional.json"

# Transactions fall in this window. It ends on the reference data's latest
# transaction date and stays before the payoff reference date.
HISTORY_END = date(2026, 11, 11)
HISTORY_DAYS = 21
# The host asks for 20 rows per page; checking gets more than that so the
# "more transactions" paging still shows.
CHECKING_COUNT = (21, 26)
SAVINGS_COUNT = (3, 6)

CHECKING_MERCHANTS = (
    "Fictional Grocer", "Fictional Coffee Cart", "Fictional Fuel Stop",
    "Fictional Bookshop", "Fictional Pharmacy", "Fictional Hardware Store",
    "Fictional Bakery", "Fictional Transit Pass", "Fictional Streaming Service",
    "Fictional Water Utility", "Fictional Noodle Bar", "Fictional Pet Supply",
)
CHECKING_CREDITS = ("Fictional payroll deposit", "Fictional refund")
SAVINGS_CREDITS = ("Fictional savings credit", "Fictional interest credit",
                   "Fictional round-up credit")

CENT = Decimal("0.01")


def reference_data():
    """A fresh copy of the reference data set (the fixture file)."""
    return json.loads(FIXTURE.read_bytes())


def _normal(rng, mean, spread, low, high) -> Decimal:
    """An amount from a normal draw in whole cents, clipped to [low, high] cents, as an exact Decimal."""
    cents = round(min(max(rng.gauss(mean, spread), low), high))
    return Decimal(cents).scaleb(-2)


def _whole(rng, mean, spread, low, high) -> Decimal:
    """A whole number of dollars from a normal draw, clipped to [low, high] dollars."""
    return Decimal(round(min(max(rng.gauss(mean, spread), low), high)))


def _text(amount: Decimal) -> str:
    return format(amount, ".2f")


def generate(seed: int):
    """Fictional bank data for ``seed`` in the mock's structure."""
    if type(seed) is not int or not 0 <= seed <= MAX_SEED:
        raise ValueError("The demo data seed must be a whole number from 0 to 999999.")
    data = reference_data()
    if seed == REFERENCE_SEED:
        return deepcopy(data)
    rng = random.Random(seed)

    for share in data["shares"]:
        if share["alias"] == "checking":
            balance = _normal(rng, 125_000, 50_000, 15_000, 800_000)
            # A pending hold keeps available at or below the ledger balance.
            hold = _normal(rng, 5_000, 3_500, 500, 30_000) if rng.random() < 0.7 else Decimal("0.00")
            available = balance - min(hold, balance - Decimal("100.00"))
        else:
            balance = _normal(rng, 540_000, 220_000, 50_000, 3_000_000)
            available = balance
        share["balance"], share["available"] = _text(balance), _text(available)

    reference_date = date.fromisoformat(data["payoff"]["reference_date"])
    for loan in data["loans"]:
        balance = _normal(rng, 490_000, 150_000, 150_000, 1_500_000)
        regular = _whole(rng, 240, 35, 150, 400)
        minimum = (regular * rng.randint(75, 89) / 100).quantize(Decimal("1"), rounding=ROUND_FLOOR)
        past_due = _normal(rng, 3_500, 1_200, 500, 9_000)
        # Current payment due is the regular installment plus the past-due part.
        loan.update(balance=_text(balance), regular_payment=_text(regular), minimum_payment=_text(minimum),
                    past_due=_text(past_due), payment_due=_text(regular + past_due),
                    due_date=(reference_date + timedelta(days=rng.randint(5, 30))).isoformat())
        # Simple daily interest on the remaining balance at 5% to 12% a year,
        # so a payoff quote is always at least the remaining balance.
        rate = Decimal(rng.randint(500, 1200)).scaleb(-4)  # whole basis points
        data["payoff"]["daily_interest"] = _text(max((balance * rate / 365).quantize(CENT), CENT))

    shares = {share["alias"]: share["id"] for share in data["shares"]}
    rows = []
    def day():
        return HISTORY_END - timedelta(days=rng.randrange(HISTORY_DAYS))
    count = rng.randint(*CHECKING_COUNT)
    deposits = rng.randint(1, 2)
    for index in range(count):
        if index < deposits:
            description = CHECKING_CREDITS[0] if index == 0 else rng.choice(CHECKING_CREDITS)
            amount = _normal(rng, 50_000, 15_000, 15_000, 250_000)
        else:
            description = rng.choice(CHECKING_MERCHANTS)
            amount = -_normal(rng, 3_500, 2_500, 150, 40_000)
        rows.append((day(), shares["checking"], description, amount))
    for _ in range(rng.randint(*SAVINGS_COUNT)):
        rows.append((day(), shares["savings"], rng.choice(SAVINGS_CREDITS), _normal(rng, 1_000, 800, 100, 50_000)))
    rows.sort(key=lambda row: (row[0], row[1]))
    data["transactions"] = [{"share_id": share_id, "date": when.isoformat(), "description": description,
                             "amount": _text(amount), "sequence": number}
                            for number, (when, share_id, description, amount) in enumerate(rows, 1)]
    return data


def data_hash(seed: int) -> str:
    """Fingerprint stored with fixture state and checked on every reopen.

    Seed 0 keeps the original fingerprint of the fixture file's bytes; other
    seeds fingerprint ``generate(seed)``, which also depends on the file's ids.
    """
    if seed == REFERENCE_SEED:
        return hashlib.sha256(FIXTURE.read_bytes()).hexdigest()
    canonical = json.dumps(generate(seed), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def parse_seed(text) -> int:
    text = str(text).strip()
    if not text.isascii() or not text.isdigit() or not 0 <= int(text) <= MAX_SEED:
        raise ValueError("DEMO_SEED must be a whole number from 0 to 999999.")
    return int(text)


def choose_seed(environ) -> int:
    """DEMO_SEED if set, else a fresh seed from 1 to 999999."""
    if environ.get("DEMO_SEED") is not None:
        return parse_seed(environ["DEMO_SEED"])
    return random.SystemRandom().randrange(1, MAX_SEED + 1)


def seed_line(seed: int) -> str:
    line = f"Demo data seed: {seed}; set DEMO_SEED={seed} to get the same data again."
    if seed == REFERENCE_SEED:
        line += " (reference data, as in the README's checked sequence)"
    return line
