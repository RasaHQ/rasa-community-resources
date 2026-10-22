"""Interval arithmetic shared by the measurement and supervision units. Standard library only."""
import math

Z95 = 1.959964


def wald(k, n):
    """The textbook interval from Lesson 1. Fails at small n and near 0 or 1."""
    p = k / n
    half = Z95 * math.sqrt(p * (1 - p) / n)
    return max(0.0, p - half), min(1.0, p + half)


def wilson(k, n):
    """Wilson score interval: stays inside [0, 1] and does not collapse when k equals n."""
    p = k / n
    denom = 1 + Z95 ** 2 / n
    centre = (p + Z95 ** 2 / (2 * n)) / denom
    half = Z95 * math.sqrt(p * (1 - p) / n + Z95 ** 2 / (4 * n * n)) / denom
    return max(0.0, centre - half), min(1.0, centre + half)


def smallest_n_for_lower_bound(target, failures=0, limit=100000):
    """Smallest n whose Wilson lower bound reaches target when `failures` of them failed."""
    for n in range(max(failures + 1, 1), limit):
        if wilson(n - failures, n)[0] >= target:
            return n
    return None
