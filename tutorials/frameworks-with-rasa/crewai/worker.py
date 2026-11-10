"""Fixed read-only worker process; customer input is JSON, never executable code."""

import argparse
from contextlib import redirect_stdout
import io
import json
import os
import sys
from crewai import LLM
from claim_crew.handoff import ClaimSession
from claim_crew.runtime import create_claim_crew
from claim_crew.native_fixture import create_fixture

parser = argparse.ArgumentParser()
parser.add_argument("--fixture", action="store_true")
parser.add_argument("--unavailable", action="store_true")
args = parser.parse_args()
result = {"status": "incomplete", "reason": "research_unavailable"}
try:
    text = sys.stdin.read(4097)
    request = json.loads(text)
    if (
        len(text) > 4096
        or not isinstance(request, dict)
        or set(request) != {"claim_type", "question"}
    ):
        raise ValueError("request shape")
    if args.fixture:
        factory = lambda kind: create_fixture(kind, unavailable=args.unavailable)
    else:
        factory = lambda kind: create_claim_crew(
            kind, LLM(model=os.getenv("CREW_MODEL", "openai/gpt-5.5-2026-04-23"))
        )
    session = ClaimSession(factory)
    selected = session.select(request["claim_type"])
    if selected["status"] != "claim_type_selected":
        raise ValueError("claim type")
    with redirect_stdout(io.StringIO()):
        result = session.checklist(request["question"])
except Exception:
    pass
print(json.dumps(result, sort_keys=True))
