# SPDX-License-Identifier: MIT
"""Seeded, fictional demo data for the local Premier mock.

Seed 0 is the reference data set in ``mock.py``: the data the tests, the
recorded exchanges and the README's checked sequence use. Any other seed draws
different but plausible fictional amounts and transactions from
``random.Random(seed)``, so a run can be reproduced with ``DEMO_SEED=<seed>``.

Every amount is a normal draw clipped to a sensible range and rounded to whole
cents at once, so money stays in integer cents, exactly as in ``mock.ACCOUNTS``
and ``mock.TRANSACTIONS``, and is never a float. The mock turns cents into an
exact Decimal when it builds a reply model. Account ids, types and owners never
change.
"""
from __future__ import annotations

import copy
from datetime import date, timedelta
import random
import re

from .mock import ACCOUNTS, PAGE, TRANSACTIONS

REFERENCE_SEED = 0
SEED_MAX = 999_999

# Obviously fictional names only; no real company or person.
DEBIT_MERCHANTS = ("Fictional Market", "Fictional Grocer", "Fictional Pharmacy", "Fictional Gas Co",
                   "Fictional Cafe", "Fictional Bookshop", "Fictional Utility", "Fictional Hardware",
                   "Fictional Bakery", "Fictional Cinema")
CREDIT_SOURCES = ("Fictional Payroll", "Fictional Refund", "Fictional Transfer", "Fictional Deposit")

# The newest posted date in the reference data; generated history never goes past it.
LATEST_DATE = max(row[1] for rows in TRANSACTIONS.values() for row in rows)
HISTORY_DAYS = 35            # window of posted dates, ending on LATEST_DATE
MIN_TRANSACTIONS = PAGE + 1  # so the history always has a second page
MAX_TRANSACTIONS = 8
MIN_DDA_CENTS = 5_000        # USD 50.00: room for the README's USD 25 transfer


def _normal(rng: random.Random, mean: float, sd: float, low: int, high: int) -> int:
    """Whole cents from a normal draw, clipped to [low, high]."""
    return int(min(high, max(low, round(rng.gauss(mean, sd)))))


def _deposit(rng, reference):
    mean = reference["avail"]
    avail = _normal(rng, mean, 0.4 * mean, max(MIN_DDA_CENTS, mean // 4), max(MIN_DDA_CENTS, mean * 4))
    # Ledger includes items not yet available: often none, sometimes a hold.
    hold = 0 if rng.random() < 0.6 else _normal(rng, 2_500, 1_500, 100, 20_000)
    return {**reference, "avail": avail, "ledger": avail + hold}


def _loan(rng, reference):
    next_total = _normal(rng, reference["next_total"], 0.15 * reference["next_total"],
                         reference["next_total"] // 2, reference["next_total"] * 3 // 2)
    past_due = 0 if rng.random() < 0.5 else _normal(rng, next_total / 3, next_total / 10, 1_000, next_total)
    pmt_due = next_total + past_due  # as in the reference: amount due = next installment + past due
    payoff = _normal(rng, reference["payoff"], 0.3 * reference["payoff"], reference["payoff"] // 3,
                     reference["payoff"] * 3)
    payoff = max(payoff, pmt_due * 3)  # a remaining balance well above what is due now
    due = date.fromisoformat(reference["next_date"])
    next_date = due.replace(day=rng.randint(1, 28)).isoformat()
    return {**reference, "next_total": next_total, "next_date": next_date, "payoff": payoff,
            "past_due": past_due, "pmt_due": pmt_due}


def _history(rng, reference_rows):
    prefix = reference_rows[0][0].split("-")[1][0]  # "T-1005" -> "1": keeps ids per account
    count = rng.randint(MIN_TRANSACTIONS, MAX_TRANSACTIONS)
    latest = date.fromisoformat(LATEST_DATE)
    days = sorted((rng.randrange(HISTORY_DAYS) for _ in range(count)))  # 0 = newest
    rows = []
    for index, back in enumerate(days):
        if rng.random() < 0.7:
            direction, cents = "Debit", _normal(rng, 3_500, 2_500, 200, 50_000)
            description = rng.choice(DEBIT_MERCHANTS)
        else:
            direction, cents = "Credit", _normal(rng, 40_000, 25_000, 500, 300_000)
            description = rng.choice(CREDIT_SOURCES)
        ident = f"T-{prefix}{count - index:03d}"  # newest first, highest number first
        rows.append((ident, (latest - timedelta(days=back)).isoformat(), direction, cents, description))
    return rows


def generate(seed: int) -> dict:
    """Return {"accounts": ..., "transactions": ...} shaped like mock.ACCOUNTS / TRANSACTIONS."""
    if isinstance(seed, bool) or not isinstance(seed, int) or not 0 <= seed <= SEED_MAX:
        raise ValueError("The demo data seed must be a whole number from 0 to 999999.")
    if seed == REFERENCE_SEED:
        return {"accounts": copy.deepcopy(ACCOUNTS), "transactions": copy.deepcopy(TRANSACTIONS)}
    rng = random.Random(seed)
    accounts = {}
    for ident, reference in ACCOUNTS.items():
        accounts[ident] = _deposit(rng, reference) if reference["type"] == "DDA" else _loan(rng, reference)
    transactions = {ident: _history(rng, rows) for ident, rows in TRANSACTIONS.items()}
    return {"accounts": accounts, "transactions": transactions}


def choose_seed(environ) -> int:
    """DEMO_SEED if set (0..999999), else a fresh random seed from 1..999999."""
    value = environ.get("DEMO_SEED")
    if value is None:
        return random.SystemRandom().randrange(1, SEED_MAX + 1)
    text = value.strip()
    if re.fullmatch(r"[0-9]{1,6}", text) is None:
        raise ValueError("DEMO_SEED must be a whole number from 0 to 999999.")
    return int(text)


def seed_line(seed: int) -> str:
    line = f"Demo data seed: {seed}; set DEMO_SEED={seed} to get the same data again."
    if seed == REFERENCE_SEED:
        line += " (reference data, as in the README's checked sequence)"
    return line
