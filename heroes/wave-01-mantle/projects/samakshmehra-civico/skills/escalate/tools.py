"""The escalate skill has no local tools.

``escalate_complaint`` lives in the shared ``tools/`` folder: check_status
needs it as well, to raise a complaint in the same breath as reporting that it
is late, and one skill cannot reach into another skill's ``tools.py``.
"""
