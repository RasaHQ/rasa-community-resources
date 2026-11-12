# SPDX-License-Identifier: MIT
"""Private permission table for the two fictional demo callers.

The model sees only the aliases. A caller is chosen by the trusted launcher, not
by a tool argument, and an account relationship returned by the mock never
authorizes anything on its own.

Aliases carry the release's own account type codes (DDA, SDA, LOAN). The
release declares these codes but does not say which product each one names, so
this example never relabels them as checking or savings.
"""

PERMISSIONS = {
    "demo-A": {"party": "PARTY-A", "accounts": (
        ("DDA-A", "5550010001", "DDA"),
        ("SDA-A", "5550010002", "SDA"),
        ("LOAN-A", "5550019001", "LOAN"))},
    "demo-B": {"party": "PARTY-B", "accounts": (
        ("DDA-B", "5550020001", "DDA"),
        ("SDA-B", "5550020002", "SDA"),
        ("LOAN-B", "5550029001", "LOAN"))},
}
