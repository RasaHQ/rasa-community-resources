"""The handoff tool: session state in, context package out, desk notified.

This is the only place in the agent where session state crosses to a human. It
does exactly three things, in this order, and the order is the design:

    1. Collect session state — ALL of it, without judging any of it.
    2. Hand it to ``build_package_from_session``, which applies the allowlist.
    3. Deliver the resulting package to the fixture desk.

Step 1 collecting everything is deliberate. A tool that carefully picks out the
safe fields is a tool that leaks the moment someone adds a field and forgets to
update the picking. Handing the whole session to a single choke point means the
allowlist is the only thing that has to be right, and it is the only thing under
test.

What a real contact-centre integration replaces is ``deliver`` in
``handoffpkg.desk`` — see that function's docstring. It does NOT replace this
tool, and it must never be handed session state directly.
"""

from __future__ import annotations

import sys
import uuid
from pathlib import Path

from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult

# The pattern's package lives at the project root, beside agent.yml, so that the
# desk and the eval suite import the same code the agent runs. No cross-project
# import is involved: this is one runnable project importing its own module.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from handoffpkg.desk import deliver, reconstruct, unanswered_questions  # noqa: E402
from handoffpkg.redaction import (  # noqa: E402
    build_package_from_session,
    scan_freetext_risk,
)

# Where the fixture desk picks up its queue. A real integration writes to a
# contact-centre API instead; the tutorial says which call and what it must not
# receive.
_DESK_QUEUE = Path(__file__).resolve().parents[2] / "fixtures" / "desk_queue"

# Keys read at handoff time.
#
# READ THIS BEFORE TRIMMING THE LIST — the sensitive entries are here ON PURPOSE.
#
# It is tempting to read only the safe keys and be done. That would make this
# tool a second safety boundary, and a second boundary is a second thing that has
# to be kept correct as memory.yml grows. Worse, it would make the allowlist
# untestable through this path: the credentials would never reach
# `build_package_from_session`, so nothing would prove the allowlist stops them.
#
# So the credential keys are read deliberately and handed straight to the choke
# point along with everything else. `pin_attempt` and `otp_code` are declared in
# skills/dispute_transaction/memory.yml and written by that skill's tools; they
# arrive here, and they do not leave here. The allowlist is what stops them, and
# because they travel this path, the eval suite genuinely exercises it.
#
# LIMIT, stated rather than glossed: this is a NAMED list, so a memory field
# added later is not collected until someone adds it here. That is a
# completeness gap in the transfer (the desk silently misses a field), never a
# safety gap (an uncollected field cannot leak). Erring toward under-collection
# is the correct direction for the failure, but it is a real gap and the README
# does not pretend otherwise.
_MEMORY_KEYS = (
    "customer_id",
    "display_name",
    "verified_tier",
    "verified_factors",
    "channel",
    "goal",
    "goal_label",
    "goal_stage",
    # The goal's parameters -> intent.details. Omitting these was a real defect:
    # the eval suite passed on a hand-built session while the live agent shipped
    # a package with an empty `details`, so the desk still asked "which account
    # is this about?". test_the_agent_path_retires_every_desk_question now
    # exercises THIS list rather than a hand-built one.
    "account_id",
    "account_label",
    "card_last_four",
    "dispute_amount",
    "dispute_merchant",
    "dispute_date",
    "attempts_log",
    "questions_answered",
    "factors_verified",
    "confirmed_facts",
    "handoff_reason",
    # Deliberately collected, deliberately never transferred. See above.
    "pin_attempt",
    "otp_code",
)


def _split_lines(value) -> tuple[str, ...]:
    """Newline-separated memory text to a tuple, blank lines dropped.

    Type-checked rather than `str(value)`-coerced. Memory is *supposed* to hold
    text here, but if a list ever arrives, `str(["x|y"])` stringifies the repr
    and the parser downstream reads `['x` as an action name — garbage rendered
    onto a desk screen as though it were real. A list is treated as the sequence
    it already is; anything else that is not text yields nothing.
    """
    if value is None:
        return ()
    if isinstance(value, (list, tuple, set)):
        return tuple(str(item).strip() for item in value if str(item).strip())
    if not isinstance(value, str):
        return ()
    return tuple(line.strip() for line in value.splitlines() if line.strip())


def _parse_attempts(value) -> list[dict[str, str]]:
    """Parse `attempts_log` records of the form ``action|outcome|code|detail``.

    Text rather than a structured type because Rasa project memory holds scalars.
    The parsing is forgiving on missing trailing parts and strict on the first
    two, since an attempt without an outcome tells the desk nothing.
    """
    attempts: list[dict[str, str]] = []
    for line in _split_lines(value):
        parts = [part.strip() for part in line.split("|")]
        if len(parts) < 2 or not parts[0] or not parts[1]:
            continue
        attempts.append(
            {
                "action": parts[0],
                "outcome": parts[1],
                "code": parts[2] if len(parts) > 2 and parts[2] else None,
                "detail": parts[3] if len(parts) > 3 and parts[3] else None,
            }
        )
    return attempts


@tool(
    description=(
        "Transfer the caller to a human agent, carrying the full context "
        "package: verified identity and tier, structured intent, what was "
        "already attempted, and what must not be asked again. Call this instead "
        "of asking the caller to repeat anything."
    )
)
async def transfer_to_human(context: ToolContext = None) -> ToolResult:
    """Build the context package from session state and deliver it to the desk."""
    if context is None:
        return ToolResult(
            llm_response={"ok": False, "error": "no_context", "hint": "Tool requires a runtime context."}
        )

    # Step 1 — collect indiscriminately. This tool is not the safety boundary.
    session: dict = {}
    for key in _MEMORY_KEYS:
        value = context.memory.get(key)
        if value is not None:
            session[key] = value

    # Normalise the text-encoded collections into the shapes the package expects.
    raw_factors = session.get("verified_factors")
    session["verified_factors"] = _split_lines(
        raw_factors.replace(",", "\n") if isinstance(raw_factors, str) else raw_factors
    )
    session["questions_answered"] = _split_lines(session.get("questions_answered"))
    session["confirmed_facts"] = _split_lines(session.get("confirmed_facts"))
    # `factors_verified` is collected in its own right now; fall back to the
    # identity factors when the skill did not record it separately, so the two
    # spellings cannot silently diverge.
    session["factors_verified"] = (
        _split_lines(session.get("factors_verified")) or session["verified_factors"]
    )
    session["attempts"] = _parse_attempts(session.pop("attempts_log", None))

    handoff_id = f"ho_{uuid.uuid4().hex[:8]}"

    # Step 2 — the boundary. Everything above this line is untrusted input.
    package = build_package_from_session(session, handoff_id=handoff_id)

    # Advisory only, and reported as advisory. The allowlist governs session
    # KEYS; it cannot police what a caller dictated into an allowlisted free-text
    # field. Surfacing the finding is honest; calling it redaction would not be.
    freetext_risk = scan_freetext_risk(package.reason)

    # Step 3 — deliver to the fixture desk.
    _DESK_QUEUE.mkdir(parents=True, exist_ok=True)
    deliver(package, str(_DESK_QUEUE / f"{handoff_id}.json"))

    context.memory.set("handoff_id", handoff_id)

    view = reconstruct(package)
    return ToolResult(
        llm_response={
            "ok": True,
            "handoff_id": handoff_id,
            # What the desk will see. Returned so the agent can honestly tell the
            # caller what was passed on — never so it can read it back to them.
            "transferred": {
                "identity": bool(package.identity.customer_id),
                "verified_tier": package.identity.verified_tier,
                "goal": package.intent.goal,
                "attempts_carried": len(package.attempts),
                "questions_retired": len(package.do_not_repeat.questions_answered),
            },
            "withheld_fields": list(package.withheld_fields),
            "desk_still_needs_to_ask": list(unanswered_questions(package)),
            "freetext_risk": freetext_risk,
            "hint": (
                "Context package delivered. Tell the caller the handoff id and "
                "that they will not need to repeat themselves. Do not read back "
                "any withheld field."
            ),
            "_desk_preview": view.render(),
        }
    )
