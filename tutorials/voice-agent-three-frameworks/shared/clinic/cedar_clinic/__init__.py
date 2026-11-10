"""Cedar Clinic, a fictional clinic: the refill-request domain shared by all three agents.

- ``cedar_clinic.refills``: records, matching, receipts and the rules, no I/O.
- ``cedar_clinic.tools``: the tool functions every agent calls, each audited.
- ``cedar_clinic.audit``: the audit log the shared spec judges by.
- ``cedar_clinic.instructions``: the persona, rules and procedure text.

No framework imports anywhere in this package.
"""

__all__ = ["audit", "instructions", "refills", "tools"]
