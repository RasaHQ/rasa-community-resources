"""Tools for the report_problem skill.

Every branch in this flow is decided here, not in the prompt. That is the one
architectural rule this project has, and it was bought expensively: the
previous version asked the conversational model to tidy a location, choose a
category and judge a duplicate through prose instruction, and it did none of
them reliably. Anything the agent must *do* rather than *say* is a tool.
"""

from __future__ import annotations

import json
import os
import re
import sqlite3

from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult

from lib import directory, speech, store


def _fail(error: str, **extra) -> ToolResult:
    return ToolResult(llm_response={"ok": False, "error": error, **extra})


def _invalidate_review(context: ToolContext, duplicates: bool = False) -> None:
    # Unset, rather than a tool-produced False. Mantle exposes a non-null
    # llm_settable value as a past decision to its `correct` tool; False here
    # made the next "yes" replay this producer instead of approving the review.
    context.memory.set("details_verified", None)
    if duplicates:
        context.memory.set("similar_id", None)
        context.memory.set("duplicate_decision", None)


def _ready(context: ToolContext, decision: str) -> bool:
    m = context.memory
    return (m.get("details_verified") in (True, "True")
            and m.get("ward_confirmed") in (True, "True")
            and m.get("duplicate_decision") == decision
            and m.get("category") in store.routing()
            and bool(directory.extract_phone(m.get("callback_number") or ""))
            and all(str(m.get(k) or "").strip()
                    for k in ("ward_id", "ward_label", "exact_spot", "description")))


def _refine_spot(existing: str, replacement: str) -> str:
    """Keep the named building for a short relative gate correction.

    A complete new landmark still replaces the old spot verbatim. This is not
    geocoding: no direction, gate number or location is inferred.
    """
    detail = replacement.strip()
    gate = re.fullmatch(r"(?:actually[, ]+)?(?:at |near |by )?(?:the )?"
                        r"((?:other|back|rear|front|side|main) gate)[.!]?", detail, re.I)
    if not existing or not gate:
        return detail
    phrase = gate.group(1).lower()
    if re.search(r"\b(?:main|front|back|rear|side|other) gate\b", existing, re.I):
        return re.sub(r"\b(?:main|front|back|rear|side|other) gate\b", phrase,
                      existing, count=1, flags=re.I)
    if re.search(r"\bgate\b", existing, re.I):
        return re.sub(r"\bgate\b", phrase, existing, count=1, flags=re.I)
    return f"{existing}, at the {phrase}"


@tool(description="Capture all volunteered complaint details together, in any order. Omit unknown fields; never invent an answer.")
async def capture_report(problem: str = "", area: str = "", landmark: str = "",
                         callback: str = "", replace_area: bool = False,
                         replace_landmark: bool = False,
                         context: ToolContext = None) -> ToolResult:
    """Save partial intake, including location before a problem is known.

    Args:
        problem: The caller's actual problem description, not just a category.
        area: Locality or PIN as spoken; include city if supplied.
        landmark: Specific incident spot supplied by caller. Preserve previous
            useful landmarks when adding a road/gate. Omit if only area is known.
        callback: Number explicitly provided or authorised by the caller.
        replace_area: True only if the caller explicitly moves the complaint to
            another locality. False for an added road or landmark within the area.
        replace_landmark: True only for an explicit replacement of the incident
            spot. False for extra detail such as a nearby metro station or road.
    """
    if context is None:
        return _fail("no_context")
    m = context.memory
    if m.get("complaint_id"):
        return _fail("already_filed")
    was_reviewed = m.get("details_verified") in (True, "True")
    errors, location_result = [], None
    # ASR/LLM extraction sometimes puts a road in the area argument. An added
    # street must not erase the known locality. Explicit moves still re-route.
    if (area.strip() and m.get("ward_confirmed") and not replace_area
            and re.search(r"\b(marg|road|street|lane|metro|gate)\b", area, re.I)
            and not directory.find_ward(area)["matches"]):
        landmark = ", ".join(dict.fromkeys(filter(None,
            [m.get("exact_spot"), landmark.strip(), area.strip()])))
        area = ""
    vague_words = set(re.findall(r"[a-z]+", landmark.lower()))
    vague_landmark = bool(vague_words) and vague_words <= {
        "it", "is", "near", "nearby", "outside", "in", "at", "by", "my", "our",
        "the", "a", "society", "house", "home", "lane", "only", "just"}
    if vague_landmark:
        landmark = ""
    if area.strip() and (area.strip() != m.get("area_text") or not m.get("ward_confirmed")):
        previous_area = m.get("area_text")
        previous_label = m.get("ward_label")
        result = await find_ward(area, context)
        location_result = result.llm_response
        m.set("area_text", area.strip())
        candidates = json.loads(m.get("ward_candidates") or "[]")
        same_locality = len(candidates) == 1 and candidates[0]["label"] == previous_label
        if previous_area and not same_locality:
            m.set("exact_spot", None)
        if len(candidates) == 1 and not candidates[0].get("pincode_differs"):
            row = candidates[0]
            _write_ward(context, row["ward_id"], row["label"],
                        row["officer_name"], row["officer_contact"])
    if problem.strip() and problem.strip() != m.get("description"):
        result = await record_category(problem, context)
        if result.llm_response.get("ok"):
            m.set("description", problem.strip())
            _invalidate_review(context, duplicates=True)
        else:
            errors.append(result.llm_response)
    if landmark.strip():
        old_spot = m.get("exact_spot") or ""
        refined = _refine_spot(old_spot, landmark)
        if old_spot and not replace_landmark and refined == landmark.strip():
            if landmark.strip().casefold() in old_spot.casefold():
                refined = old_spot
            elif old_spot.casefold() not in landmark.casefold():
                refined = f"{old_spot}, {landmark.strip()}"
        if refined != old_spot:
            m.set("exact_spot", refined)
            _invalidate_review(context, duplicates=True)
    if callback.strip() and callback.strip() != m.get("callback_number"):
        result = await record_callback_number(callback, context)
        if not result.llm_response.get("ok"):
            errors.append(result.llm_response)
    missing = []
    if not m.get("category") or not m.get("description"):
        missing.append("problem")
    if m.get("ward_confirmed") not in (True, "True"):
        missing.append("locality_or_pin")
    if not m.get("exact_spot"):
        missing.append("landmark")
    if not m.get("callback_number"):
        missing.append("callback")
    if was_reviewed and not m.get("details_verified") and not missing and not errors:
        return await _refresh_corrected_review(context, "details")
    return ToolResult(llm_response={
        "ok": not errors, "errors": errors, "missing": missing,
        "location_result": location_result,
        "saved": {key: m.get(key) for key in
                  ("description", "ward_label", "exact_spot", "callback_number")},
        "hint": ("Ask: What is your society or building called? Do not repeat the problem question yet. "
                 if vague_landmark and not m.get("exact_spot") else "") +
                "Ask only for missing details, unless the caller is finishing another detail. "
                "Do not repeat saved details as a question. Review a unique locality in the final summary, not a separate ward question. "
                "If complete, continue to duplicate check without a spoken acknowledgement.",
    })


@tool(description="Read the completed draft once before Rasa asks for submission consent. Does not save or approve submission.")
async def prepare_report_summary(context: ToolContext = None, **_ignored) -> ToolResult:
    if context is None:
        return _fail("no_context")
    m = context.memory
    decision = m.get("duplicate_decision")
    if m.get("details_verified") in (True, "True") and _ready(context, decision):
        return ToolResult(llm_response={"ok": True, "already_read_out_to_the_caller": True,
            "hint": "The unchanged draft was already read back. Do not repeat it; continue to submission consent."})
    # This flag means read-back ready, not caller consent. The write tool's
    # requires_confirmation is the sole consent gate, enforced by Rasa.
    m.set("details_verified", True)
    if decision not in ("new", "attach") or not _ready(context, decision):
        m.set("details_verified", None)
        return _fail("incomplete_draft")
    m.set("details_verified", None)
    route = store.routing()[m.get("category")]
    summary = (f"{m.get('description')} — {m.get('exact_spot')}, "
               f"{m.get('ward_label')}. ")
    if decision == "attach":
        summary += "Your details will join the existing demo report, keeping its original target."
    else:
        summary += (f"This will go to {route['department']} in the demo, "
                    f"with a {route['sla_days']}-day target.")
    digits = "zero one two three four five six seven eight nine".split()
    ending = " ".join(digits[int(d)] for d in m.get("callback_number")[-4:])
    summary += f" Callback ending in {ending}."
    await context.send(summary)
    m.set("details_verified", True)
    return ToolResult(llm_response={"ok": True, "already_read_out_to_the_caller": True,
        "hint": "Proceed to the write step; Rasa asks for consent. Do not repeat the summary or add another approval question."})


async def record_category(category: str, context: ToolContext = None) -> ToolResult:
    """Set the complaint category, and with it the department and target days.

    Args:
        category: One of pothole, garbage, water_supply, streetlight,
            drainage, stray_animals.

    Note the name. ``set_`` is a reserved tool-name prefix in rasa-pro 3.20 —
    a tool called ``set_category`` fails to build, with an error that does not
    mention the prefix.
    """
    key = store.normalise_category(category)
    routes = store.routing()
    if key not in routes:
        return _fail("unsupported_category",
                     supported=list(routes.keys()),
                     helpline=directory._directory()["helpline"])

    route = routes[key]
    if context is not None:
        if context.memory.get("category") != key:
            _invalidate_review(context, duplicates=True)
        context.memory.set("category", key)
        context.memory.set("category_spoken", route["spoken"])
        context.memory.set("department", route["department"])
        context.memory.set("sla_days", str(route["sla_days"]))

    return ToolResult(llm_response={
        "ok": True,
        "category": key,
        "spoken": route["spoken"],
        "department": route["department"],
        "target_days": route["sla_days"],
    })


async def find_ward(area: str, context: ToolContext = None) -> ToolResult:
    """Match a spoken area or PIN code against the ward directory.

    Args:
        area: Whatever the caller said about where the problem is — the
            locality, the PIN code, or both. Pass it whole and unedited; this
            tool handles the filler words and the spoken digits itself.

    Finding nothing is a normal result, not a failure. The caller is asked once
    more, and if that also finds nothing the flow routes to the general
    grievance cell rather than dead-ending — which is what a human operator
    who cannot place an address does too.
    """
    result = directory.find_ward(area)
    matches = result["matches"]

    attempts = 1
    if context is not None:
        _invalidate_review(context, duplicates=True)
        context.memory.set("ward_confirmed", False)
        for field in ("ward_id", "ward_label", "ward_officer", "ward_officer_contact"):
            context.memory.set(field, None)
        context.memory.set("ward_candidates", json.dumps(matches))
        if not matches:
            attempts = int(context.memory.get("ward_attempts") or 0) + 1
            context.memory.set("ward_attempts", str(attempts))

    if not matches:
        # Two tries, then take it anyway — and do the routing here rather than
        # returning an instruction to do it. Counting attempts is exactly the
        # bookkeeping that gets dropped when the model is also running a
        # conversation: told "you have tried twice, now call use_general_cell",
        # it complied about half the time and otherwise asked a third time.
        # The caller who cannot name their own locality is the one person on
        # this line who least needs to be asked again.
        if attempts >= 2 and context is not None:
            return await use_general_cell(context)
        return ToolResult(llm_response={
            "ok": True,
            "found": 0,
            "attempts": attempts,
            "heard_pincode": result["pincode"],
            "hint": "Ask once for a better-known locality nearby, or the PIN code.",
        })

    return ToolResult(llm_response={
        "ok": True,
        "found": len(matches),
        "matched_on": result["matched_on"],
        "options": [
            {
                "number": i + 1,
                "say": f"{m['label']}, ward {m['ward_id'].lstrip('W').lstrip('0') or m['ward_id']}",
                "locality": m["label"],
                "pincode": m["pincode"],
                # True when the directory puts this locality in a different PIN
                # to the one the caller read out. Surfaced so the agent can
                # mention it; never resolved silently in either direction.
                "pincode_differs": m["pincode_differs"],
            }
            for i, m in enumerate(matches)
        ],
    })


#: How people actually pick from a spoken list.
_ORDINAL_WORDS = {
    "first": 1, "one": 1, "1st": 1,
    "second": 2, "two": 2, "2nd": 2,
    "third": 3, "three": 3, "3rd": 3,
}
_AGREEMENT = frozenset({
    "yes", "yeah", "yep", "yup", "ya", "haan", "han", "correct", "right",
    "true", "ok", "okay", "sure", "that", "one", "it", "same", "exactly",
    "please", "do", "go", "ahead", "fine", "good", "perfect", "confirm",
})


def _pick(choice, count: int) -> int:
    """Turn whatever the caller said into a zero-based index, or -1.

    Callers do not answer a one-item list with "one". They say "yes", and an
    agent that then insists on a number has turned a confirmation into an
    obstacle — observed live, three turns in a row, on a list with a single
    entry.
    """
    text = str(choice or "").strip().lower()
    if text.lstrip("-").isdigit():
        return int(text) - 1

    words = [w for w in re.findall(r"\w+", text) if w]
    if any(w in {"no", "not", "nope", "neither", "wrong"} for w in words):
        return -1
    for word in words:
        if word in _ORDINAL_WORDS:
            return _ORDINAL_WORDS[word] - 1
    # An agreement is only unambiguous when there is one thing to agree to.
    if count == 1 and any(word in _AGREEMENT for word in words):
        return 0
    return -1


@tool(description="Confirm which of the ward options the caller picked.")
async def confirm_ward(choice: str = "", context: ToolContext = None) -> ToolResult:
    """Lock in the ward the caller agreed to.

    Args:
        choice: What the caller said — the option number, an ordinal like
            "the second one", or a plain "yes" when only one was offered.
    """
    if context is None:
        return _fail("no_context")

    # A unique lookup is already provisionally routed. A redundant model call
    # must not turn it into a demand that the caller repeat a ward option.
    if context.memory.get("ward_confirmed") in (True, "True"):
        return ToolResult(llm_response={"ok": True, "already_selected": True,
            "locality": context.memory.get("ward_label"),
            "ward": context.memory.get("ward_id"),
            "hint": "Routing is already selected. Continue intake without asking a ward question. For a changed area use capture_report."})

    raw = context.memory.get("ward_candidates") or "[]"
    try:
        candidates = json.loads(raw)
    except (TypeError, ValueError):
        candidates = []

    index = _pick(choice, len(candidates))
    named = str(choice or "").strip().casefold()
    for i, candidate in enumerate(candidates):
        if named in {str(candidate.get(key) or "").casefold()
                     for key in ("label", "locality", "ward_id")} - {""}:
            index = i
            break
    if not candidates or index < 0 or index >= len(candidates):
        return _fail("no_such_option", offered=len(candidates),
                     heard=str(choice))

    picked = candidates[index]
    _write_ward(context, picked["ward_id"], picked["label"],
                picked["officer_name"], picked["officer_contact"])
    return ToolResult(llm_response={
        "ok": True,
        "locality": picked["label"],
        "ward": picked["ward_id"],
        "officer": picked["officer_name"],
    })


async def use_general_cell(context: ToolContext = None, **_ignored) -> ToolResult:
    """Take the complaint anyway when the directory cannot place the address.

    The caller keeps whatever they said about the location — it goes on the
    work order verbatim — and the grievance cell sorts out the ward. Being
    unable to name your own ward is not a reason to be turned away from a
    civic line.
    """
    if context is None:
        return _fail("no_context")
    cell = directory.general_cell()
    _write_ward(context, cell["ward_id"], cell["label"],
                cell["officer_name"], cell["officer_contact"])

    # Said here, because a caller who has just failed twice to name their own
    # locality should be told the complaint is still going through. Left to the
    # model this was silently skipped and the next question simply arrived.
    await context.send(
        "I could not place that locality, but I can still take the complaint. "
        "It will go to the grievance cell, who will work out the ward."
    )

    return ToolResult(llm_response={
        "ok": True,
        "already_read_out_to_the_caller": True,
        "routed_to": cell["label"],
        "contact": cell["officer_contact"],
    })


def _write_ward(context: ToolContext, ward_id: str, label: str,
                officer: str, contact: str) -> None:
    _invalidate_review(context, duplicates=True)
    context.memory.set("ward_id", ward_id)
    context.memory.set("ward_label", label)
    context.memory.set("ward_officer", officer)
    context.memory.set("ward_officer_contact", contact)
    context.memory.set("ward_confirmed", True)


async def record_callback_number(number: str, context: ToolContext = None) -> ToolResult:
    """Validate and store a callback number.

    Args:
        number: The number as the caller said it — spoken digits are fine.

    Ten digits or it is rejected, because a work order with nine digits on it
    wastes a crew's afternoon and nobody finds out until they are already
    standing in the wrong street.
    """
    digits = directory.extract_phone(number)
    if not digits:
        return _fail("incomplete_number", heard=number,
                     hint="Read the ten digits back and ask them to repeat it.")
    if context is not None:
        _invalidate_review(context)
        context.memory.set("callback_number", digits)
    return ToolResult(llm_response={"ok": True, "number": digits,
                                    "spoken": " ".join(digits)})


@tool(description="Record or correct a detail in the current unfiled complaint and require a fresh read-back.")
async def revise_report(field: str, value: str,
                        context: ToolContext = None) -> ToolResult:
    """Accept a caller's correction without restarting the entire intake.

    Args:
        field: category, area, exact_spot, description, or callback_number.
        value: The replacement detail explicitly supplied by the caller.
    """
    if context is None:
        return _fail("no_context")
    if context.memory.get("complaint_id"):
        return _fail("already_filed", hint="Use complaint tracking for the filed report.")
    was_reviewed = context.memory.get("details_verified") in (True, "True")
    if not str(value or "").strip():
        return _fail("correction_required")
    if field == "category":
        result = await record_category(value, context)
        if result.llm_response.get("ok"):
            context.memory.set("description", None)
            _invalidate_review(context, duplicates=True)
            return ToolResult(llm_response={"ok": True,
                "hint": "Category changed. Ask what is wrong with this new issue; keep the location and callback. Do not read the previous issue's description."})
        return result
    if field == "area":
        context.memory.set("exact_spot", None)
        context.memory.set("ward_attempts", "0")
        return await find_ward(value, context)
    if field == "callback_number":
        result = await record_callback_number(value, context)
        if result.llm_response.get("ok") and was_reviewed:
            return await _refresh_corrected_review(context, field, check_duplicates=False)
        return result
    if field not in {"exact_spot", "description"}:
        return _fail("unknown_correction_field")
    context.memory.set(field, _refine_spot(context.memory.get(field) or "", value)
                       if field == "exact_spot" else value.strip())
    _invalidate_review(context, duplicates=True)
    if was_reviewed:
        return await _refresh_corrected_review(context, field)
    if not context.memory.get("description"):
        hint = "Continue intake: ask for a short description of the problem."
    elif not context.memory.get("callback_number"):
        hint = "Continue intake: ask which ten-digit callback number to use."
    else:
        hint = "Check duplicates again, then read the revised summary for confirmation."
    return ToolResult(llm_response={"ok": True, "corrected": field,
                                    "hint": hint})


async def _refresh_corrected_review(context: ToolContext, field: str,
                                    check_duplicates: bool = True) -> ToolResult:
    """Refresh a changed draft atomically; never rely on a spoken paraphrase."""
    match = await find_similar_open(context) if check_duplicates else ToolResult()
    if context.memory.get("duplicate_decision") in ("new", "attach"):
        result = await prepare_report_summary(context)
        if result.llm_response.get("ok"):
            return ToolResult(llm_response={"ok": True, "corrected": field,
                "already_read_out_to_the_caller": True,
                "hint": "The corrected summary was sent. Ask for permission to submit these corrected details once, then wait for the caller's NEXT answer before resolving the pending write confirmation. Do not repeat the summary."})
    return ToolResult(llm_response={"ok": True, "corrected": field,
        "duplicate_check": match.llm_response,
        "hint": "Ask same or different for this changed location. Do not submit or resolve the pending write until the duplicate decision and a fresh summary are complete."})


@tool(description="Check whether this problem is already reported in this ward.")
async def find_similar_open(context: ToolContext = None, **_ignored) -> ToolResult:
    """Look for an open complaint of the same kind in the same ward.

    Coarse on purpose. The previous version measured metres between two
    geocoded points to decide whether two people meant the same pothole — a
    precise answer to a question that cannot be answered precisely. Same
    problem, same neighbourhood, still open: then ask the caller, who is the
    only one who actually knows.
    """
    if context is None:
        return _fail("no_context")

    category = context.memory.get("category")
    ward_id = context.memory.get("ward_id")
    if not category or not ward_id:
        return _fail("not_ready")

    # A repeat caller can describe the very same incident. Do not exclude them.
    # The general cell is an unplaced queue, so sharing it proves no proximity.
    others = (store.open_similar(category, ward_id)
              if ward_id != directory.general_cell()["ward_id"] else [])
    context.memory.set("similar_id", None)

    if not others:
        # Nothing to decide, so nothing to ask and nothing for the model to
        # get wrong. Most calls take this branch and never hear the word
        # "duplicate" at all.
        context.memory.set("duplicate_decision", "new")
        return ToolResult(llm_response={"ok": True, "found": 0,
                                        "duplicate_decision": "new"})

    match = others[0]
    context.memory.set("similar_id", match["complaint_id"])

    # Asked here, not left to an instruction. Observed failure: the model
    # would sometimes set duplicate_decision to "new" and move on without
    # putting the question to the caller at all — quietly opening a second
    # complaint for the same blocked drain, which is the exact thing this
    # step exists to prevent.
    context.memory.set("duplicate_decision", None)

    return ToolResult(llm_response={
        "ok": True,
        "found": len(others),
        "ask": "Say where the open complaint is and roughly how long ago it "
               "was reported, then ask whether this is the same one or a "
               "different one.",
        # The reference is ours, not theirs. Reading another citizen's
        # complaint number aloud tells this caller nothing and hands them
        # somebody else's filing reference.
        "where": match["exact_spot"],
        "reported_days_ago": speech.say_days(
            max(0, match["sla_days"] - match["days_left"])),
        "status": match["status_spoken"],
    })


@tool(description="Add this caller to an existing complaint instead of filing a new one.")
async def attach_to_existing(context: ToolContext = None, **_ignored) -> ToolResult:
    """Record that this caller is reporting the same incident."""
    if context is None:
        return _fail("no_context")

    complaint_id = context.memory.get("similar_id")
    if not complaint_id:
        return _fail("nothing_to_attach_to")
    if not _ready(context, "attach"):
        return _fail("not_ready", hint="Complete the details and confirm the summary first.")

    phone = context.memory.get("callback_number") or ""
    existing = store.get_complaint(complaint_id)
    if (not existing or existing["category"] != context.memory.get("category")
            or existing["ward_id"] != context.memory.get("ward_id")):
        return _fail("duplicate_changed", hint="Check for matching open reports again.")
    try:
        updated = store.attach_report(complaint_id, phone,
                                      context.memory.get("exact_spot"),
                                      context.memory.get("description"))
    except sqlite3.Error:
        return _fail("register_unavailable")
    if updated is None:
        return _fail("not_found", complaint_id=complaint_id)

    context.memory.set("complaint_id", updated["complaint_id"])
    await context.send(
        f"Your details are saved on the existing demo complaint. "
        f"Your tracking reference is {updated['spoken_id']}. "
        f"It keeps its {updated['department']} assignment and original target of "
        f"{speech.say_date(updated['target_on'])}. "
        "No new complaint was created. Ask me to check this reference or your callback number."
    )

    return ToolResult(llm_response={
        "ok": True,
        "already_read_out_to_the_caller": True,
        "complaint_id": updated["complaint_id"],
        "spoken_id": updated["spoken_id"],
        "status": updated["status_spoken"],
        "days_left": updated["days_left"],
    })


@tool(description="File the complaint and return its reference number.")
async def file_complaint(context: ToolContext = None, **_ignored) -> ToolResult:
    """Write the complaint to the register.

    Takes no arguments. Everything it needs is already in memory, put there by
    the tools above and guarded by ``tool_constraints`` in the skill — so this
    cannot run against a half-collected complaint, whatever the model believes.
    """
    if context is None:
        return _fail("no_context")

    if os.getenv("CIVICO_FORCE_FILE_FAILURE") == "1":
        return _fail("register_unavailable")

    if context.memory.get("complaint_id"):
        return ToolResult(llm_response={"ok": True, "already_filed": True,
            "complaint_id": context.memory.get("complaint_id")})
    if not _ready(context, "new"):
        return _fail("not_ready", hint="Complete the details and confirm the summary first.")

    # Re-read the fixed routing data; stale or generated memory is not a route.
    route = store.routing()[context.memory.get("category")]
    context.memory.set("department", route["department"])
    context.memory.set("sla_days", str(route["sla_days"]))

    try:
        record = store.insert_complaint(
            phone=context.memory.get("callback_number"),
            category=context.memory.get("category"),
            ward_id=context.memory.get("ward_id"),
            locality=context.memory.get("ward_label"),
            exact_spot=context.memory.get("exact_spot") or "",
            description=context.memory.get("description") or "",
            department=route["department"],
            sla_days=int(route["sla_days"]),
            citizen_id=context.memory.get("caller_id") or None,
        )
    except sqlite3.Error:
        return _fail("register_unavailable")

    context.memory.set("complaint_id", record["complaint_id"])

    # Spoken here rather than left to the model. This one sentence is what the
    # caller is on the phone for, and leaving it to an instruction made it a
    # coin flip: the model would sometimes read the reference back and
    # sometimes mark the step done and say nothing at all. A verbatim
    # `on_success` response cannot carry it either, because a response cannot
    # interpolate the values. So the tool says it.
    if record["ward_id"] == directory.general_cell()["ward_id"]:
        # No ward officer to name yet — saying "the Grievance Cell duty officer
        # is the ward officer for General Grievance Cell" is a sentence only a
        # template could produce.
        who = "Its demo assignment is the grievance cell; the local team is not identified yet"
    else:
        who = (f"Its demo assignment is {route['department']}, "
               f"with {context.memory.get('ward_officer')} for {record['locality']}")

    await context.send(
        f"Your report is saved. Your reference is {record['spoken_id']}. "
        f"{who}. The demo target is {speech.say_date(record['target_on'])}. "
        "Ask me to check this reference or your callback number for its status."
    )

    return ToolResult(llm_response={
        "ok": True,
        "already_read_out_to_the_caller": True,
        "complaint_id": record["complaint_id"],
        "spoken_id": record["spoken_id"],
        "department": record["department"],
        "officer": context.memory.get("ward_officer"),
        "locality": record["locality"],
        "target_days": record["sla_days"],
        "target_on": record["target_on"],
    })
