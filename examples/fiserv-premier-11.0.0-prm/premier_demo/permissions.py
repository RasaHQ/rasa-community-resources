# SPDX-License-Identifier: MIT
"""Private permission table for the two fictional demo callers.

The model sees only the aliases. A caller is chosen by the trusted launcher, not
by a tool argument, and an account relationship returned by the mock never
authorizes anything on its own.
"""

PERMISSIONS = {
    "demo-A": {"party": "PARTY-A", "accounts": (
        ("checking-A", "5550010001", "DDA"),
        ("bills-A", "5550010002", "DDA"),
        ("loan-A", "5550019001", "LOAN"))},
    "demo-B": {"party": "PARTY-B", "accounts": (
        ("checking-B", "5550020001", "DDA"),
        ("bills-B", "5550020002", "DDA"),
        ("loan-B", "5550029001", "LOAN"))},
}
