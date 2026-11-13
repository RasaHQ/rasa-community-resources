# SPDX-License-Identifier: MIT
"""Seeded fictional account data for the local mock.

Seed 0 is the reference data set: the fixed ACCOUNTS in mock.py, which the
tests and the README's checked sequence use. Any other seed draws different,
plausible fictional amounts and dates from its own random.Random(seed), so one
seed always gives the same data. Account ids, types and owners never change.

This release carries no transaction history and no payoff (see the README), so
there are no transactions to vary: only balances and next loan payments.
Every draw is a normal distribution clipped to a sensible range. Money is whole
cents (int), as in mock.py: each draw is rounded to a whole number of cents at
once, so no amount is ever a float. The mock turns cents into an exact Decimal
when it builds a reply model.
"""
from __future__ import annotations

import copy
from datetime import date, timedelta
import random

from .mock import ACCOUNTS

REFERENCE_SEED = 0
MAX_SEED = 999_999

# Ranges in cents. Every generated value is clipped into its range.
DEPOSIT_AVAIL_RANGE = {"DDA": (10_000, 2_500_000), "SDA": (1_000, 5_000_000)}
PENDING_RANGE = (100, 50_000)        # ledger minus available, DDA only
PRINCIPAL_RANGE = (2_500, 200_000)
INTEREST_RANGE = (100, 50_000)
DUE_DATE_SHIFT_DAYS = 10             # next payment date: reference date +/- this many days

# Normal spread of each draw, as a share of its reference value.
DEPOSIT_SPREAD = {"DDA": 0.4, "SDA": 0.5}
PENDING_MEAN_CENTS, PENDING_SD_CENTS, PENDING_SHARE = 2_500, 1_500, 0.5
PRINCIPAL_SPREAD, INTEREST_SPREAD = 0.25, 0.30


def _cents(rng: random.Random, mean: float, sd: float, bounds: tuple[int, int]) -> int:
    """Whole cents from a normal draw, clipped into bounds."""
    low, high = bounds
    return min(high, max(low, round(rng.gauss(mean, sd))))


def generate(seed: int) -> dict:
    """Account data in the shape mock.ACCOUNTS uses. Seed 0 is a copy of the reference."""
    if isinstance(seed, bool) or not isinstance(seed, int) or not 0 <= seed <= MAX_SEED:
        raise ValueError(f"The demo data seed must be a whole number from 0 to {MAX_SEED}.")
    data = copy.deepcopy(ACCOUNTS)
    if seed == REFERENCE_SEED:
        return data
    rng = random.Random(seed)
    for ident in sorted(data):
        account = data[ident]
        kind = account["type"]
        if kind in DEPOSIT_AVAIL_RANGE:
            avail = _cents(rng, account["avail"], DEPOSIT_SPREAD[kind] * account["avail"], DEPOSIT_AVAIL_RANGE[kind])
            pending = 0
            # Only a DDA shows a pending difference, about half the time; ledger >= available.
            if kind == "DDA" and rng.random() < PENDING_SHARE:
                pending = _cents(rng, PENDING_MEAN_CENTS, PENDING_SD_CENTS, PENDING_RANGE)
            account["avail"], account["ledger"] = avail, avail + pending
        else:  # LOAN: total is always principal + interest
            principal = _cents(rng, account["principal"], PRINCIPAL_SPREAD * account["principal"],
                               PRINCIPAL_RANGE)
            interest = _cents(rng, account["interest"], INTEREST_SPREAD * account["interest"],
                              (INTEREST_RANGE[0], min(INTEREST_RANGE[1], principal)))
            shift = rng.randint(-DUE_DATE_SHIFT_DAYS, DUE_DATE_SHIFT_DAYS)
            account["next_date"] = (date.fromisoformat(account["next_date"]) + timedelta(days=shift)).isoformat()
            account["principal"], account["interest"] = principal, interest
            account["total"] = principal + interest
    return data


def choose_seed(environ) -> int:
    """DEMO_SEED when set (0..999999), else a fresh seed from 1..999999."""
    raw = environ.get("DEMO_SEED")
    if raw is None:
        return random.SystemRandom().randrange(1, MAX_SEED + 1)
    text = raw.strip()
    if not text.isascii() or not text.isdigit() or not 0 <= int(text) <= MAX_SEED:
        raise ValueError(f"DEMO_SEED must be a whole number from 0 to {MAX_SEED}.")
    return int(text)


def seed_line(seed: int) -> str:
    line = f"Demo data seed: {seed}; set DEMO_SEED={seed} to get the same data again."
    if seed == REFERENCE_SEED:
        line += " (reference data, as in the README's checked sequence)"
    return line
