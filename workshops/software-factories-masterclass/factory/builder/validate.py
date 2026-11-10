"""What the builder can see: whether Mantle's own authoring checks accept the project. Offline, no keys.

    python validate.py
"""
import logging
import sys
from pathlib import Path

import structlog

structlog.configure(wrapper_class=structlog.make_filtering_bound_logger(logging.CRITICAL))
from rasa.mantle.validation import collect_project_findings  # noqa: E402

found = collect_project_findings(Path(__file__).resolve().parent / "product")
for finding in found:
    print(finding.code, "-", finding.message)
print("Mantle found nothing to object to." if not found else "%d finding(s)." % len(found))
sys.exit(1 if found else 0)
