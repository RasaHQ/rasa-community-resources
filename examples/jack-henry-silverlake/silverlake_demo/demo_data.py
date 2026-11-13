# SPDX-License-Identifier: MIT
"""Seeded fictional data for the SilverLake mock.

Seed 0 is the reference data set: an exact copy of CUSTOMERS, ACCOUNTS and
HISTORY in mock.py, which the tests, the start-up compatibility check and the
README's checked sequence use. Any other seed draws different, plausible
fictional amounts and transactions from its own random.Random(seed), so the
same seed always gives the same data. Account ids, types, owners, product
descriptions, loan dates and payoff quote dates never change.

Every amount is a normal draw clipped to a sensible range and rounded to whole
cents at once, so money stays in integer cents, as in mock.py, and is never a
float. The mock turns cents into an exact Decimal when it builds a reply
dataclass.
"""
from __future__ import annotations

import copy
from datetime import date, timedelta
from decimal import ROUND_HALF_EVEN, Decimal
import random

from .mock import ACCOUNTS, CUSTOMERS, HISTORY

REFERENCE_SEED = 0
MAX_SEED = 999_999

# Obviously fictional names only.
SPENDING = ("Fictional Market", "Fictional Pharmacy", "Fictional Gas Co", "Fictional Grocer", "Fictional Cafe",
            "Fictional Bookshop", "Fictional Hardware", "Fictional Utility Co", "Fictional Diner",
            "Fictional Cinema")
CHECKING_CREDITS = ("Fictional Refund", "Fictional Cashback")
SAVINGS_CREDITS = ("Fictional Transfer", "Fictional Deposit", "Fictional Interest")

HISTORY_DAYS = 35  # transaction dates fall within this window, ending on the reference's latest date
CHECKING_ROWS = (4, 8)  # more than the mock's page size of 3, so a second page shows
SAVINGS_ROWS = (3, 5)
DEPOSIT_FLOOR = 5000  # every checking and savings balance stays at least USD 50.00


def reference() -> dict:
    """A deep copy of the reference data, in the structure SilverLakeMock(data=...) takes."""
    return {"customers": copy.deepcopy(CUSTOMERS), "accounts": copy.deepcopy(ACCOUNTS),
            "history": copy.deepcopy(HISTORY)}


def _normal(rng: random.Random, mean: float, spread: float, low: float, high: float) -> int:
    """Whole cents from a normal draw, clipped to [low, high]."""
    return round(min(max(rng.gauss(mean, spread), low), high))


def _deposit(rng, account):
    ref = account["cur"]
    cur = _normal(rng, ref, 0.35 * ref, max(0.4 * ref, DEPOSIT_FLOOR + 2000), 2.5 * ref)
    hold = 0
    if account["type"] == "D" and rng.random() < 0.5:  # a pending debit: available below ledger
        hold = _normal(rng, 2500, 1500, 500, min(20000, cur // 4))
    return {**account, "cur": cur, "avail": cur - hold}


def _loan(rng, account):
    regular = _normal(rng, account["regular"], 0.15 * account["regular"],
                      0.6 * account["regular"], 1.4 * account["regular"])
    past_due = 0
    if rng.random() < 0.4:  # sometimes one part-payment is behind
        past_due = _normal(rng, 0.33 * regular, 0.1 * regular, 0.1 * regular, regular)
    quotes = sorted(account["payoff"].items())
    first_date, first_amount = quotes[0]
    first = _normal(rng, first_amount, 0.3 * first_amount, 0.5 * first_amount, 2.0 * first_amount)
    first = max(first, 10 * (regular + past_due))  # a payoff is well above one installment
    # Later quote dates keep the reference's growth from the first date, so a later
    # quote is never lower than an earlier one.
    payoff = {when: int((Decimal(first) * amount / first_amount).to_integral_value(ROUND_HALF_EVEN))
              for when, amount in quotes}  # exact: whole cents, no float
    payoff[first_date] = first
    return {**account, "regular": regular, "past_due": past_due, "due": regular + past_due, "payoff": payoff}


def _history(rng, account, rows, latest):
    kind = account["type"]
    count = rng.randint(*(CHECKING_ROWS if kind == "D" else SAVINGS_ROWS))
    credits = [cents for _, cents, _ in rows if cents > 0] or [10000]
    big = max(credits)
    entries = []
    for position in range(count):
        if kind == "D":
            # Always one payroll and at least one purchase; the rest mostly purchases.
            pick = "payroll" if position == 0 else "spend" if position == 1 else rng.choices(
                ("spend", "credit", "payroll"), (0.75, 0.15, 0.10))[0]
            if pick == "payroll":
                entry = (_normal(rng, big, 0.25 * big, 0.5 * big, 2.0 * big), "Fictional Payroll")
            elif pick == "credit":
                entry = (_normal(rng, 2500, 1500, 300, 10000), rng.choice(CHECKING_CREDITS))
            else:
                entry = (-_normal(rng, 3500, 2500, 300, 25000), rng.choice(SPENDING))
        else:
            if position > 0 and rng.random() < 0.2:
                entry = (-_normal(rng, big / 2, 0.25 * big, 500, big), "Fictional Transfer")
            else:
                entry = (_normal(rng, big, 0.6 * big, 500, 3.0 * big), rng.choice(SAVINGS_CREDITS))
        entries.append(entry)
    days = sorted((rng.randrange(HISTORY_DAYS) for _ in range(count)))  # 0 = the latest date
    rng.shuffle(entries)
    return [((latest - timedelta(days=day)).isoformat(), cents, text) for day, (cents, text) in zip(days, entries)]


def generate(seed: int) -> dict:
    """Mock data for a seed: the reference data for 0, seeded fictional data otherwise."""
    if isinstance(seed, bool) or not isinstance(seed, int) or not 0 <= seed <= MAX_SEED:
        raise ValueError("The demo data seed must be a whole number from 0 to 999999.")
    if seed == REFERENCE_SEED:
        return reference()
    rng = random.Random(seed)
    latest = max(date.fromisoformat(posted) for rows in HISTORY.values() for posted, _, _ in rows)
    accounts = {}
    for ident, account in ACCOUNTS.items():
        accounts[ident] = _loan(rng, account) if account["type"] == "L" else _deposit(rng, account)
    history = {ident: _history(rng, ACCOUNTS[ident], rows, latest) for ident, rows in HISTORY.items()}
    return {"customers": copy.deepcopy(CUSTOMERS), "accounts": accounts, "history": history}


def choose_seed(environ) -> int:
    """DEMO_SEED when set (0..999999), otherwise a fresh random seed from 1 to 999999."""
    text = environ.get("DEMO_SEED")
    if text is None:
        return random.SystemRandom().randrange(1, MAX_SEED + 1)
    text = text.strip()
    if not text.isdigit() or not text.isascii() or int(text) > MAX_SEED:
        raise ValueError("DEMO_SEED must be a whole number from 0 to 999999.")
    return int(text)


def seed_line(seed: int) -> str:
    line = f"Demo data seed: {seed}; set DEMO_SEED={seed} to get the same data again."
    if seed == REFERENCE_SEED:
        line += " (reference data, as in the README's checked sequence)"
    return line
