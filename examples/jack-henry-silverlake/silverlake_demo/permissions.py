# SPDX-License-Identifier: MIT
"""Private permission table for the two fictional demo callers.

The model sees only the aliases. A caller is chosen by the trusted launcher, not
by a tool argument, and an account search result never authorizes on its own.
"""

PERMISSIONS = {
    "demo-A": {"customer": "C100001", "accounts": (
        ("checking-A", "1001001", "D"),
        ("savings-A", "1001002", "S"),
        ("loan-A", "7001001", "L"))},
    "demo-B": {"customer": "C200002", "accounts": (
        ("checking-B", "2001001", "D"),
        ("savings-B", "2001002", "S"),
        ("loan-B", "8001001", "L"))},
}
