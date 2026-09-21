"""SIM swap skill tools (auto-discovered).

Four tools, and one of them is the reason this file exists:

    request_sim_swap   the side effect. Its first statement is the guard.
    send_swap_verification / confirm_swap_verification
                       the only writers of the verification record.
    check_swap_status  reads what the fixture store says; never infers.

WHY THE GUARD LIVES INSIDE THE TOOL
-----------------------------------
`skill.md` tells the model never to offer an SMS code to the line being moved
and never to fall back to knowledge questions. That prose is a routing control:
it shapes what the model tries. It is not an execution control. The prose can
be edited, the model can be swapped, a `requires:` can be mistyped. So the
decision that binds is `evaluate_swap`, called on the first line of
`request_sim_swap`, before the ICCID is looked at and before anything is
written. A refusal returns `ok: False` and no reference, because a refusal that
carried a reference would be a queued swap wearing a denial's clothes.

NO REAL CARRIER LIVES HERE
--------------------------
Nothing is sent. The push code below is a fixture, the store is fictional and
the "queue" is a SQLite table seeded from `data/source/`. A real deployment
replaces `send_swap_verification` (a push provider) and the insert in
`request_sim_swap` (the provisioning system). The policy in `lib/sim_swap.py`
and the guard placement do not move.
"""

from __future__ import annotations

import hmac
import logging
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult

from lib.database import Database, customer_id_from_context
from lib.sim_swap import (
    CIRCULAR_VERIFICATION,
    INDEPENDENT_CHANNELS,
    KNOWLEDGE_CHANNELS,
    KNOWLEDGE_ONLY,
    LINE_CHANNELS,
    NO_VERIFICATION,
    TARGET_CHANGED,
    SwapDecision,
    SwapVerification,
    coerce_verification,
    evaluate_swap,
    line_digits,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Fixtures. NOT credentials.
# ---------------------------------------------------------------------------

# The code the demo app "shows" on the registered device, spelled as a caller
# would say it. A real push code is generated per attempt, expires in minutes,
# is single-use, and is never in source. This one is none of those things,
# because it guards a SQLite table.
DEMO_PUSH_CODE = "six two eight four"

# Attempts before lockout. Small on purpose: this is the factor an attacker is
# guessing against.
RETRY_BUDGET = 2

# Memory keys, named once so no caller can typo one into a permanently empty
# read. Declared in skills/sim_swap/memory.yml.
VERIFICATION_KEY = "swap_verification"
ATTEMPTS_KEY = "swap_code_attempts"
LOCKED_OUT_KEY = "swap_locked_out"
REFERENCE_KEY = "swap_reference"
STATUS_KEY = "swap_status"
CALL_STARTED_KEY = "swap_call_started_at"

# What the caller is told about the push destination before they are verified.
# Never the device's label, id or type: an unverified caller who learns "the
# tablet" has learned something about the account.
NEUTRAL_DEVICE_PHRASE = "a device already registered to the account"

# Stored in the verification record instead of the device id, because memory
# can be shown to the model and the model talks to an unverified caller.
PUSH_DESTINATION = "registered_device"

# Tests point this at a temporary file. None means the project's data/telco.db.
DATABASE_PATH: Optional[Path] = None

_ICCID_RE = re.compile(r"^89\d{17,18}$")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def redact(secret: object) -> str:
    """Render a code for a log line without disclosing it.

    Returns a length, never the text. On a voice channel the transcript of the
    turn where the caller read the code aloud is already a plaintext copy; the
    tool layer must not add a second one to the logs.
    """
    if not isinstance(secret, str) or not secret:
        return "<empty>"
    return f"<redacted:{len(secret)} chars>"


def _normalize_spoken(spoken: object) -> str:
    """Compare what the caller SAID, not how the ASR punctuated it."""
    if not isinstance(spoken, str):
        return ""
    return " ".join(spoken.lower().replace(".", " ").replace(",", " ").split())


def _database() -> Database:
    """Open the demo store on disk, so a write is visible to the next reader.

    `Database()` seeds into an in-memory connection the first time and copies
    it to disk. Writes made on that first connection would never reach the
    file, so a queued swap could vanish before `check_swap_status` looks for
    it. Opening twice guarantees the returned connection is the file.

    An older `data/telco.db` made before this skill existed has no SIM swap
    tables; `_ensure_swap_tables` adds and seeds them rather than failing.
    """
    path = DATABASE_PATH
    target = path or (Path(__file__).resolve().parents[2] / "data" / "telco.db")
    if not target.exists():
        Database(path).connection.close()
    db = Database(path)
    _ensure_swap_tables(db)
    return db


def _ensure_swap_tables(db: Database) -> None:
    import json

    for table in ("mobile_lines", "registered_devices", "sim_swaps"):
        definition = db.table_definitions[table]
        db.connection.execute(definition["create_statement"])
        (count,) = db.run_query(f"SELECT COUNT(*) FROM {table}")  # noqa: S608 - fixed names
        source = db.source_data_path / f"{table}.json"
        if count == 0 and source.is_file():
            db.insert_data(table, json.loads(source.read_text(encoding="utf-8")))
    db.commit()


def _customer_line(db: Database, customer_id: str, line: str) -> Optional[str]:
    """Return the stored line if `line` belongs to this customer, else None."""
    wanted = line_digits(line)
    if not wanted:
        return None
    rows = db.run_query(
        "SELECT line FROM mobile_lines WHERE customer_id = ?",
        (customer_id,),
        one_record=False,
    )
    for (stored,) in rows or []:
        if line_digits(stored) == wanted:
            return stored
    return None


def _parse_utc(value: object) -> Optional[datetime]:
    """Parse an ISO timestamp as UTC. None for anything unparseable."""
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _earliest_event_time(context: Optional[ToolContext]) -> Optional[datetime]:
    """When the conversation began, from the tracker's first event timestamp."""
    try:
        events = list(context.events) if context is not None else []
    except Exception:  # noqa: BLE001 - no tracker (tests, discovery probes)
        return None
    stamps = [
        e.timestamp for e in events
        if isinstance(getattr(e, "timestamp", None), (int, float))
    ]
    if not stamps:
        return None
    return datetime.fromtimestamp(min(stamps), tz=timezone.utc)


def _call_started_at(context: Optional[ToolContext]) -> datetime:
    """The start of this call, fixed on first use and remembered.

    Order of preference: a value already in memory; the timestamp of the
    earliest tracker event; the current time. Whichever is found first is
    written to memory, so every later tool call in the session compares
    against the same instant. Falling back to "now" is conservative: it can
    only make a device look newer, never older, than the call.
    """
    stored = _parse_utc(context.memory.get(CALL_STARTED_KEY)) if context is not None else None
    if stored is not None:
        return stored
    started = _earliest_event_time(context) or datetime.now(timezone.utc)
    if context is not None:
        context.memory.set(CALL_STARTED_KEY, started.strftime("%Y-%m-%dT%H:%M:%SZ"))
    return started


def _trusted_push_device(
    db: Database, customer_id: str, call_started: datetime
) -> Optional[tuple]:
    """The one device an app push may go to: active, and registered before the call.

    `registered_at < call_started`, compared as timestamps. A `pending` device,
    one with no registration time, or one registered after the call began was
    enrolled on the word of the caller we are trying to verify. It is never
    chosen.
    """
    rows = db.run_query(
        """
        SELECT device_id, label, registered_at FROM registered_devices
        WHERE customer_id = ? AND app_push = 1 AND status = 'active'
        ORDER BY registered_at
        """,
        (customer_id,),
        one_record=False,
    )
    for device_id, label, registered_at in rows or []:
        registered = _parse_utc(registered_at)
        if registered is not None and registered < call_started:
            return device_id, label
    return None


def _read_verification(context: Optional[ToolContext]) -> Optional[SwapVerification]:
    if context is None:
        return None
    return coerce_verification(context.memory.get(VERIFICATION_KEY))


def _write_verification(context: Optional[ToolContext], record: SwapVerification) -> None:
    if context is not None:
        context.memory.set(VERIFICATION_KEY, record.to_json())


def _discard_verification(context: Optional[ToolContext]) -> None:
    """Forget the verification. Used on a target change, lockout, or use.

    Leaves the attempt counter alone. If re-sending a push reset it, a caller
    could guess once, ask for a fresh push, and guess again, forever.
    """
    if context is not None:
        context.memory.set(VERIFICATION_KEY, None)


def _attempts(context: Optional[ToolContext]) -> int:
    if context is None:
        return 0
    try:
        return int(float(context.memory.get(ATTEMPTS_KEY) or 0))
    except (TypeError, ValueError):
        return 0


# ---------------------------------------------------------------------------
# The guard
# ---------------------------------------------------------------------------


class SwapRefused(Exception):
    """Raised when the policy refuses a swap. Carries the decision, not prose."""

    def __init__(self, decision: SwapDecision) -> None:
        self.decision = decision
        super().__init__(f"sim swap refused: {decision.reason}")


def require_independent_verification(line: str, context: Optional[ToolContext]) -> SwapDecision:
    """Enforce the policy against the verification in memory.

    Raises rather than returning a falsy value: a return value can be ignored
    by a caller who forgot to check it, an exception cannot. A missing context
    is treated as unverified, not as a reason to skip the check.
    """
    stored = None if context is None else context.memory.get(VERIFICATION_KEY)
    if context is not None and context.memory.get(LOCKED_OUT_KEY) is True:
        stored = None
    decision = evaluate_swap(line, stored)
    if not decision.allowed:
        raise SwapRefused(decision)
    return decision


_REFUSAL_HINTS = {
    NO_VERIFICATION: (
        "No independent verification is in place. Offer an app push to a "
        "registered device or a store visit with photo ID. If neither is "
        "possible, hand off to the identity team with @skill.human_handoff."
    ),
    KNOWLEDGE_ONLY: (
        "A PIN, date of birth or security answer cannot authorise a SIM swap. "
        "Do not ask another knowledge question. Offer an app push or a store "
        "visit with photo ID."
    ),
    CIRCULAR_VERIFICATION: (
        "A code sent to the line being replaced cannot authorise replacing it. "
        "Do not offer an SMS or call to that line. Offer an app push or a "
        "store visit with photo ID."
    ),
    TARGET_CHANGED: (
        "The caller verified a different line. That verification has been "
        "discarded. Confirm which line they want and verify again for it."
    ),
}


def _refuse(exc: SwapRefused, context: Optional[ToolContext]) -> ToolResult:
    """Turn a refusal into something the agent can act on, disclosing nothing.

    `ok: False`, a reason code and a hint. No reference, no status, no ICCID
    echo: nothing that could be read aloud as if the swap had happened.

    A record that was refused for what it IS (knowledge, circular, wrong line)
    is discarded, so it cannot be re-presented later in the call.
    """
    decision = exc.decision
    logger.info(
        "sim_swap_refused reason=%s channel=%s",
        decision.reason,
        decision.channel or "none",
    )
    if decision.reason in (TARGET_CHANGED, KNOWLEDGE_ONLY, CIRCULAR_VERIFICATION):
        _discard_verification(context)
    return ToolResult(
        llm_response={
            "ok": False,
            "refused": True,
            "reason": decision.reason,
            "hint": (
                "The SIM swap did NOT happen and nothing was queued. "
                + _REFUSAL_HINTS.get(decision.reason, _REFUSAL_HINTS[NO_VERIFICATION])
            ),
        }
    )


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@tool(
    description=(
        "Start verification for a SIM swap on one of the customer's lines. "
        "Channel must be app_push (to a device registered before this call) or "
        "store_id_check. SMS or a call to the line being swapped is refused, and "
        "so is any knowledge question."
    )
)
async def send_swap_verification(
    line: str = "",
    channel: str = "",
    context: ToolContext = None,
) -> ToolResult:
    """Issue a verification bound to `line`. Sends nothing real.

    Args:
        line: The line the caller wants moved to a new SIM, such as 555-0142.
        channel: app_push or store_id_check.
    """
    wanted = (channel or "").strip().lower()

    if context is not None and context.memory.get(LOCKED_OUT_KEY) is True:
        return ToolResult(
            llm_response={
                "ok": False,
                "outcome": "locked_out",
                "handoff_required": True,
                "hint": "Verification is locked on this call. Use @skill.human_handoff.",
            }
        )

    if wanted in KNOWLEDGE_CHANNELS:
        return ToolResult(
            llm_response={
                "ok": False,
                "reason": KNOWLEDGE_ONLY,
                "hint": _REFUSAL_HINTS[KNOWLEDGE_ONLY],
            }
        )

    if wanted in LINE_CHANNELS:
        # Refused before sending. Delivering a code to the line being moved
        # would hand the approval to whoever controls that line now.
        return ToolResult(
            llm_response={
                "ok": False,
                "reason": CIRCULAR_VERIFICATION,
                "hint": _REFUSAL_HINTS[CIRCULAR_VERIFICATION],
            }
        )

    if wanted not in INDEPENDENT_CHANNELS:
        return ToolResult(
            llm_response={
                "ok": False,
                "error": "unsupported_channel",
                "hint": "Use app_push or store_id_check.",
            }
        )

    call_started = _call_started_at(context)
    customer_id = customer_id_from_context(context)
    db = _database()
    stored_line = _customer_line(db, customer_id, line)
    if stored_line is None:
        return ToolResult(
            llm_response={
                "ok": False,
                "error": "line_not_found",
                "hint": "Ask which of their lines they mean. Do not guess a number.",
            }
        )

    # A new verification replaces any earlier one, including one issued for a
    # different line. Only one record exists at a time.
    _discard_verification(context)

    if wanted == "store_id_check":
        _write_verification(
            context,
            SwapVerification(
                channel="store_id_check",
                destination="store",
                issued_for_line=stored_line,
                passed=False,
            ),
        )
        return ToolResult(
            llm_response={
                "ok": True,
                "store_visit_required": True,
                "remote_activation": False,
                "line_ending": line_digits(stored_line)[-4:],
                "hint": (
                    "Tell the caller to bring photo ID and the new SIM to a "
                    "Telecom of Rasa store. Staff complete the swap there. "
                    "Nothing is queued from this call."
                ),
            }
        )

    device = _trusted_push_device(db, customer_id, call_started)
    if device is None:
        return ToolResult(
            llm_response={
                "ok": False,
                "reason": "no_independent_path",
                "handoff_required": True,
                "hint": (
                    "There is no device that was registered before this call "
                    "to send a push to. Do not activate remotely. Offer a store visit with "
                    "photo ID, or hand off to the identity team with "
                    "@skill.human_handoff."
                ),
            }
        )

    device_id, _device_label = device
    _write_verification(
        context,
        SwapVerification(
            channel="app_push",
            destination=PUSH_DESTINATION,
            issued_for_line=stored_line,
            passed=False,
            registered_before_call=True,
        ),
    )
    logger.info("sim_swap_push_sent device=%s line_ending=%s", device_id, stored_line[-4:])
    return ToolResult(
        llm_response={
            "ok": True,
            "delivered": True,
            "channel": "app_push",
            "destination": NEUTRAL_DEVICE_PHRASE,
            "line_ending": line_digits(stored_line)[-4:],
            "hint": (
                "Tell the caller a code was sent to the app on a device already "
                "registered to the account, and ask them to read it back. Do "
                "NOT name or describe the device, and do NOT state the code; "
                "you know neither."
            ),
        }
    )


@tool(
    description=(
        "Check the code the caller read back from the app push. Only valid "
        "after send_swap_verification with app_push."
    )
)
async def confirm_swap_verification(
    code: str = "",
    context: ToolContext = None,
) -> ToolResult:
    """Mark the pending app-push verification as passed, or count a failure.

    The code is compared, redacted for the log, and dropped. It is never
    written to memory and never returned.

    Args:
        code: What the caller read back, as transcribed.
    """
    if context is not None and context.memory.get(LOCKED_OUT_KEY) is True:
        return ToolResult(
            llm_response={
                "ok": False,
                "outcome": "locked_out",
                "handoff_required": True,
                "hint": "Verification is locked on this call. Use @skill.human_handoff.",
            }
        )

    pending = _read_verification(context)
    if pending is None or pending.channel != "app_push":
        return ToolResult(
            llm_response={
                "ok": False,
                "error": "no_pending_push",
                "hint": (
                    "There is no app push waiting for a code. A store ID check "
                    "is completed in the store, not over the phone."
                ),
            }
        )

    used = _attempts(context) + 1
    matched = hmac.compare_digest(
        _normalize_spoken(code).encode(), _normalize_spoken(DEMO_PUSH_CODE).encode()
    )
    logger.info(
        "sim_swap_code_attempt matched=%s attempt=%d value=%s", matched, used, redact(code)
    )

    if matched:
        _write_verification(
            context,
            SwapVerification(
                channel=pending.channel,
                destination=pending.destination,
                issued_for_line=pending.issued_for_line,
                passed=True,
                registered_before_call=pending.registered_before_call,
            ),
        )
        if context is not None:
            context.memory.set(ATTEMPTS_KEY, 0.0)
        return ToolResult(
            llm_response={
                "ok": True,
                "outcome": "passed",
                "line_ending": line_digits(pending.issued_for_line)[-4:],
                "note": "Verified for this line only. Changing the line needs a new verification.",
            }
        )

    if used >= RETRY_BUDGET:
        _discard_verification(context)
        if context is not None:
            context.memory.set(LOCKED_OUT_KEY, True)
        return ToolResult(
            llm_response={
                "ok": False,
                "outcome": "locked_out",
                "handoff_required": True,
                "hint": (
                    "Too many wrong codes. Do NOT retry, do NOT switch to another "
                    "factor, and do NOT request the swap. Use @skill.human_handoff."
                ),
            }
        )

    if context is not None:
        context.memory.set(ATTEMPTS_KEY, float(used))
    return ToolResult(
        llm_response={
            "ok": False,
            "outcome": "retry",
            "attempts_remaining": RETRY_BUDGET - used,
            "hint": "The code did not match. Offer one more try. Nothing has been requested.",
        }
    )


@tool(
    description=(
        "Queue a SIM swap that moves a line to a new SIM. Refused unless the "
        "line was verified through an independent channel on this call. A "
        "queued request is not an active SIM."
    )
)
async def request_sim_swap(
    line: str = "",
    new_iccid: str = "",
    context: ToolContext = None,
) -> ToolResult:
    """Queue the swap. The guard below is the first statement, on purpose.

    Args:
        line: The line to move, such as 555-0142.
        new_iccid: The 19 or 20 digit number printed on the new SIM card.
    """
    try:
        require_independent_verification(line, context)
    except SwapRefused as exc:
        return _refuse(exc, context)

    iccid = "".join(ch for ch in (new_iccid or "") if ch.isdigit())
    if not _ICCID_RE.match(iccid):
        return ToolResult(
            llm_response={
                "ok": False,
                "error": "invalid_iccid",
                "hint": "Ask the caller to read the full number printed on the new SIM card.",
            }
        )

    customer_id = customer_id_from_context(context)
    db = _database()
    stored_line = _customer_line(db, customer_id, line)
    if stored_line is None:
        return ToolResult(
            llm_response={
                "ok": False,
                "error": "line_not_found",
                "hint": "That line is not on this account. Nothing was queued.",
            }
        )

    reference = f"SWP-{uuid.uuid4().hex[:8].upper()}"
    requested_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    db.connection.execute(
        db.table_definitions["sim_swaps"]["insert_statement"],
        (reference, customer_id, stored_line, iccid[-4:], "queued", requested_at),
    )
    db.commit()

    # Single use: the verification that authorised this request is spent.
    _discard_verification(context)
    if context is not None:
        context.memory.set(REFERENCE_KEY, reference)
        context.memory.set(STATUS_KEY, "queued")

    logger.info("sim_swap_queued reference=%s line_ending=%s", reference, stored_line[-4:])
    return ToolResult(
        llm_response={
            "ok": True,
            "reference": reference,
            "status": "queued",
            "active": False,
            "line_ending": line_digits(stored_line)[-4:],
            "receipt_proves": (
                "A swap request is queued. It does NOT prove the new SIM is "
                "active. Say only that it is queued, and that the old SIM keeps "
                "working until the swap completes."
            ),
        }
    )


@tool(
    description=(
        "Report the stored status of a SIM swap request by reference. Says "
        "queued or active exactly as recorded."
    )
)
async def check_swap_status(
    reference: str = "",
    context: ToolContext = None,
) -> ToolResult:
    """Read the status from the store. Never infers `active` from a request.

    Args:
        reference: The swap reference, such as SWP-1001.
    """
    customer_id = customer_id_from_context(context)
    db = _database()
    row = db.run_query(
        "SELECT line, status, requested_at FROM sim_swaps WHERE reference = ? AND customer_id = ?",
        ((reference or "").strip().upper(), customer_id),
        one_record=True,
    )
    if not row:
        return ToolResult(
            llm_response={
                "ok": False,
                "error": "reference_not_found",
                "hint": "Ask the caller to repeat the reference. Do not guess a status.",
            }
        )

    line, status, requested_at = row
    if context is not None:
        context.memory.set(STATUS_KEY, status)
    return ToolResult(
        llm_response={
            "ok": True,
            "reference": (reference or "").strip().upper(),
            "status": status,
            "active": status == "active",
            "line_ending": line_digits(line)[-4:],
            "requested_at": requested_at,
        }
    )
