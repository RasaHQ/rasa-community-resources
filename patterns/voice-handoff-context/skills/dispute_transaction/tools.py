"""Fixture dispute flow — the source of the state a handoff has to carry.

The dispute exists to produce a realistic handoff, not to be a dispute feature.
It is chosen because it generates all four sections of the context package
naturally:

    identity + tier   the caller is resolved and verified to `medium`
    intent            structured: goal, account, card, amount, merchant, date
    attempts          a factor that succeeded, a delivery that failed, a
                      dispute that was BLOCKED on tier
    do_not_repeat     the questions answered on the way through

And it ends where handoffs actually happen: at a step the agent is not
authorised to complete. The tier gate here is deliberately thin — this pattern
does not own authentication. ``patterns/voice-auth-stepup`` does, and it decides
tiers from the action being attempted. What this pattern owns is what happens to
the state at the moment the agent gives up.

NOTE ON THE SENSITIVE FIELDS BELOW: ``pin_attempt`` and ``otp_code`` are written
into session state on purpose. They are what a real auth flow leaves behind, and
a redaction contract that is only ever tested against fields nobody writes is not
tested at all.
"""

from __future__ import annotations

import sys
from pathlib import Path

from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from handoffpkg.schema import tier_at_least  # noqa: E402

# Fictional signed-in caller. A real deployment resolves this from the
# authenticated session or channel identity.
_CALLER = {
    "customer_id": "cust_00417",
    "display_name": "Jordan Rivera",
    # The tier this demo caller reached. Owned by voice-auth-stepup in a real
    # composition; hard-coded here so the handoff has something true to carry.
    "verified_tier": "medium",
    "verified_factors": "knowledge_passphrase",
    "channel": "voice",
    "account_id": "acc_checking",
    "account_label": "Everyday Checking",
    "card_last_four": "4821",
}

_CHARGES = [
    {"id": "txn_c101", "date": "2026-08-29", "merchant": "Northgate Fuel", "amount": "$248.00"},
    {"id": "txn_c102", "date": "2026-08-27", "merchant": "Blue Harbor Market", "amount": "$42.18"},
    {"id": "txn_c103", "date": "2026-08-25", "merchant": "Northline Transit", "amount": "$3.50"},
]

# Raising a dispute is irreversible and fraud-attractive, so it needs the top
# tier. The demo caller is at `medium`, which is what makes the handoff happen.
_DISPUTE_MIN_TIER = "high"


def _append(context: ToolContext, key: str, line: str) -> None:
    """Append a line to a newline-separated memory field."""
    existing = context.memory.get(key)
    lines = [item for item in str(existing or "").splitlines() if item.strip()]
    if line not in lines:
        lines.append(line)
    context.memory.set(key, "\n".join(lines))


@tool(
    description=(
        "Resolve who the caller is and the verification tier they reached. "
        "Call this before anything account-specific."
    )
)
async def load_caller_context(context: ToolContext = None) -> ToolResult:
    """Seed identity, tier, and the questions that need never be asked again."""
    if context is None:
        return ToolResult(llm_response={"ok": False, "error": "no_context"})

    for key in (
        "customer_id", "display_name", "verified_tier", "verified_factors", "channel",
        # The account and card the caller is asking about. These are what make
        # `intent.details` non-empty, which is what retires "which account is
        # this about?" on the desk. Omitting them was a real defect: the eval
        # suite passed on a hand-built session while the live agent produced a
        # package that still made the desk ask.
        "account_id", "account_label", "card_last_four",
    ):
        context.memory.set(key, _CALLER[key])
    context.memory.set("goal", "dispute_transaction")
    context.memory.set("goal_label", "Dispute a card transaction")
    context.memory.set("goal_stage", "stated")

    # Every question resolved here is a question the human desk must not repeat.
    for question in (
        "Can I take your name?",
        "Can you confirm your date of birth?",
        "Which account is this about?",
    ):
        _append(context, "questions_answered", question)
    _append(context, "confirmed_facts", "Caller consented to the call being recorded.")
    _append(
        context,
        "attempts_log",
        "verify_passphrase|succeeded||Caller answered the knowledge factor on the first try.",
    )

    # --- deliberately sensitive, deliberately in session state ---------------
    # This is what a real auth step leaves behind. It is written here so the
    # redaction contract is exercised against a field that actually exists,
    # rather than against a hypothetical one. It must never reach the package;
    # tests/test_handoff_context.py is what proves it does not.
    context.memory.set("pin_attempt", "4242")

    return ToolResult(
        llm_response={
            "ok": True,
            "customer_id": _CALLER["customer_id"],
            "display_name": _CALLER["display_name"],
            "verified_tier": _CALLER["verified_tier"],
            "account_label": _CALLER["account_label"],
            "card_last_four": _CALLER["card_last_four"],
        }
    )


@tool(description="List the caller's recent card charges so they can pick the disputed one.")
async def list_recent_charges(context: ToolContext = None) -> ToolResult:
    """Return the fixture charge list."""
    if context is not None:
        context.memory.set("goal_stage", "in_progress")
        _append(context, "questions_answered", "What are you calling about today?")
    return ToolResult(llm_response={"charges": _CHARGES, "charge_count": len(_CHARGES)})


@tool(
    description=(
        "Raise a dispute for the selected transaction. Requires a high "
        "verification tier; returns insufficient_tier otherwise."
    )
)
async def raise_dispute(context: ToolContext = None) -> ToolResult:
    """Attempt the dispute, and record the attempt whichever way it goes.

    Recording the FAILURE is the part that matters. An agent that only logs
    successes hands a human a package that looks like nothing was tried, and the
    human retries the path that already failed — which is the specific waste this
    pattern is built to remove.
    """
    if context is None:
        return ToolResult(llm_response={"ok": False, "error": "no_context"})

    txn_id = context.memory.get("disputed_txn_id")
    if not txn_id:
        return ToolResult(
            llm_response={"ok": False, "error": "no_transaction_selected",
                          "hint": "Ask which charge they are disputing first."}
        )

    charge = next((c for c in _CHARGES if c["id"] == str(txn_id)), None)
    if charge is None:
        return ToolResult(
            llm_response={"ok": False, "error": "unknown_transaction", "transaction_id": txn_id,
                          "hint": "Call list_recent_charges and pick an id from the result."}
        )

    context.memory.set("disputed_txn_label", f"{charge['merchant']} {charge['amount']}")

    tier = str(context.memory.get("verified_tier") or "unverified")
    if not tier_at_least(tier, _DISPUTE_MIN_TIER):
        # A second factor would be attempted here in a real flow. It is simulated
        # as a delivery failure because "the OTP did not arrive" is the most
        # common real reason a caller ends up on a human's line — and because a
        # failed attempt is exactly what the human must not repeat.
        _append(
            context,
            "attempts_log",
            "send_otp_sms|failed|delivery_failed|"
            "Carrier rejected the SMS twice. Do not resend to this number.",
        )
        _append(
            context,
            "attempts_log",
            f"raise_dispute|blocked|insufficient_tier|"
            f"Dispute needs tier '{_DISPUTE_MIN_TIER}'; caller is at '{tier}'.",
        )
        context.memory.set("goal_stage", "blocked")

        # --- deliberately sensitive, deliberately in session state -----------
        # The code that was generated for the failed delivery. Live at the moment
        # of handoff, which is precisely why it must not cross.
        context.memory.set("otp_code", "889134")

        return ToolResult(
            llm_response={
                "ok": False,
                "error": "insufficient_tier",
                "required_tier": _DISPUTE_MIN_TIER,
                "current_tier": tier,
                "hint": (
                    "Do not retry and do not attempt step-up here. Explain that a "
                    "specialist must complete it, set handoff_reason, and use the "
                    "human handoff skill."
                ),
            }
        )

    _append(context, "attempts_log", f"raise_dispute|succeeded||Dispute opened for {charge['id']}.")
    context.memory.set("goal_stage", "in_progress")
    return ToolResult(
        llm_response={"ok": True, "transaction_id": charge["id"], "case_id": "case_44120"}
    )
