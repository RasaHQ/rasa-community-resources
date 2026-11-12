# SPDX-License-Identifier: MIT
"""Out-of-band reset of the FICTIONAL mock exercise. Not MCP, not HTTP, not a tool.

Run it only while the example is stopped: it needs the journal's exclusive lock,
so a running backend makes it refuse. It records an audit row with the hash of
the prior journal and old/new epochs, preserves old unknown entries as history,
and starts a new fictional exercise. It never says an old transfer failed or
succeeded and never authorizes resending it.
"""
import argparse
import os
from pathlib import Path

from .host import Journal, Refused


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reason", required=True, help="Why you are starting a new fictional exercise.")
    parser.add_argument("--acknowledge-unresolved", action="store_true",
                        help="I understand an earlier unknown outcome stays unresolved in history.")
    args = parser.parse_args()
    if not args.acknowledge_unresolved:
        parser.error("add --acknowledge-unresolved to confirm you understand")
    path = Path(os.environ.get("PREMIER_JOURNAL") or
                Path(__file__).resolve().parents[1] / "var" / "private" / "journal.sqlite3")
    try:
        epoch = Journal(path).reset_fixture(args.reason)
    except Refused as refusal:
        print("Not reset: " + str(refusal))
        return 1
    print(f"New fictional exercise started (epoch {epoch}); the audit row was written.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
