#!/usr/bin/env python3
"""Demonstrate the guard, without a model in the loop.

WHY THIS SCRIPT AND NOT AN EVAL SUITE
-------------------------------------
The claim this project makes is a claim about a Python function: given a
destination the caller supplied during the call and a verification level below
`high`, `reissue_card` does not order a card. That claim is about the process,
not about the model — so it is provable by calling the function, and no
conversation test is needed or sufficient.

A conversation-level test would tell you the model asked for a code, which is a
different and weaker claim: it says the usual path is usually taken. This says
the unusual path is closed. Run it with no licence, no API key, and no network.

Exit status is 0 only if every case behaves as stated.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.cards import reissue_card  # noqa: E402

ON_FILE = ("14 Wexley Row", "Bristol", "BS1 4TR")
STATED = ("9 Elsewhere Lane", "Leeds", "LS1 9ZZ")

GREEN, RED, DIM, RESET = "\033[32m", "\033[31m", "\033[2m", "\033[0m"


async def main() -> int:
    failures = 0

    def check(label: str, got: dict, *, ordered: bool, result: str) -> None:
        nonlocal failures
        ok = got["ok"] is ordered and got["result"] == result
        mark = f"{GREEN}✓{RESET}" if ok else f"{RED}✗{RESET}"
        print(f"  {mark} {label}")
        print(f"      {DIM}-> ok={got['ok']} result={got['result']}{RESET}")
        if not ok:
            failures += 1
            print(f"      {RED}expected ok={ordered} result={result}{RESET}")

    print("\nAn address the bank already held:")
    check(
        "unverified caller cannot order a card at all",
        await reissue_card("CARD-9931", *ON_FILE, auth_tier="none"),
        ordered=False,
        result="step_up_required",
    )
    first = await reissue_card("CARD-9931", *ON_FILE, auth_tier="medium")
    check("verified caller can, at medium", first, ordered=True, result="ok")

    print("\nAn address supplied during the call:")
    check(
        "medium is NOT enough — this is the account-takeover path",
        await reissue_card("CARD-2204", *STATED, auth_tier="medium"),
        ordered=False,
        result="step_up_required",
    )
    check(
        "high is enough — the path is priced, not banned",
        await reissue_card("CARD-2204", *STATED, auth_tier="high"),
        ordered=True,
        result="ok",
    )

    print("\nFailing closed on input the guard did not expect:")
    for junk in ("admin", "", "TRUE", "high ish", "none", "3"):
        check(
            f"auth_tier={junk!r} is refused, not interpreted",
            await reissue_card("CARD-9931", *STATED, auth_tier=junk),
            ordered=False,
            result="step_up_required",
        )

    print("\nCasing is normalised, because ASR casing is not a security signal:")
    check(
        "auth_tier='HIGH' is the same tier as 'high'",
        await reissue_card("CARD-2204", *STATED, auth_tier="HIGH"),
        ordered=True,
        result="duplicate",
    )

    print("\nThe same request twice posts one card:")
    again = await reissue_card("CARD-9931", *ON_FILE, auth_tier="medium")
    check("second attempt reports duplicate", again, ordered=True, result="duplicate")
    same = again.get("reference") == first.get("reference")
    mark = f"{GREEN}✓{RESET}" if same else f"{RED}✗{RESET}"
    print(f"  {mark} and returns the SAME reference ({again.get('reference')})")
    if not same:
        failures += 1

    print("\nA refusal never carries a reference:")
    denied = await reissue_card("CARD-2204", *STATED, auth_tier="low")
    has_ref = "reference" in denied
    mark = f"{GREEN}✓{RESET}" if not has_ref else f"{RED}✗{RESET}"
    print(f"  {mark} refused payload has no reference key")
    if has_ref:
        failures += 1

    if failures:
        print(f"\n{RED}✗ {failures} case(s) did not behave as stated.{RESET}\n")
        return 1
    print(f"\n{GREEN}✓ Every case behaved as stated.{RESET}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
