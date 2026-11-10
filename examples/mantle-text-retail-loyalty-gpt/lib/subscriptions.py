"""Willow Shop subscription changes and the case guard, with no Rasa imports.

Everything here is fictional fixture data read from ``lib/fixtures/``. The
guard applies the casebook contract for ``retail-loyalty`` (vendored as
``lib/fixtures/case-contract.json``) when ``apply_subscription_change`` runs.

Request rules, checked before any command reaches the subscription service:

- ``change_type_confirmed`` (``wrong_subscription_change``): the change type
  the model asks to run is the one selected, and the engine's confirmation
  question for that exact change tag (``WS-SUB-3301 stop_renewal r7``) and its
  plain-words label ("stop the renewal, not an immediate cancellation") was
  sent and answered. Stopping renewal, pausing and cancelling now are three
  different commands; the model cannot run one it did not have confirmed.
- ``entitlement_delta_disclosed`` (``benefit_loss_hidden``): the effective
  date and the entitlement line read back to the member are exactly what the
  subscription service computes for that change at the subscription's current
  revision. If the subscription changed after the question (a new revision),
  the old disclosure no longer counts.

Receipt rule, checked on what the service returns after the command:

- ``change_receipt_verified`` (``change_not_recorded``): the service's answer
  names the same subscription and command, with the effective time and
  entitlements that were disclosed. An unknown result (a timeout) or a
  mismatch leaves the change ``pending``. Recovery reads the original request
  key and revision back from the service (``check_change_status``); it never
  sends another command.

The receipt is a subscription-change reference with the effective time and
the remaining entitlements, copied from the service's answer.

Facts are computed here from trusted data and the conversation's events. A
fact that is not exactly ``True`` fails its rule, as in the lab's
``evaluate``.

The organisation guard runs at import and is an allowlist: the fixture's
organisation must be the casebook contract's own fictional retailer, marked
fictional, and so must every other organisation field in the fixture.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Callable, Optional

FIXTURES = Path(__file__).resolve().parent / "fixtures"
CONTRACT_FILE = FIXTURES / "case-contract.json"
DATA_FILE = FIXTURES / "willow_shop_subscriptions.json"

# Mantle renders at most this many characters of one memory value into the
# prompt and cuts the rest silently (rasa/mantle/prompts/memory_lines.py,
# MAX_MEMORY_VALUE_LENGTH on 3.21.0.dev5). Every value a tool writes to memory
# is one short field; tests/test_guard.py checks every fixture value.
MEMORY_VALUE_LIMIT = 100

# The engine's confirmation question for apply_subscription_change
# (skills/subscription_change/responses.yml). Mantle stamps the response name
# on the BotUttered event under this metadata key.
CONFIRM_UTTER = "utter_confirm_subscription_change"
UTTER_ACTION_KEY = "utter_action"

# The tools send the member the change reference themselves through
# ToolContext.send (found in the HarborCover claim-intake build: a silent
# complete_skill otherwise hides the receipt). The `receipt-in-result-only`
# variant sets this to False.
TOOL_SENDS_RECEIPT = True

# Skill memory keys the tools write (skills/subscription_change/memory.yml).
MEMORY_KEYS = ("change_subscription", "change_tag", "change_label", "change_effective", "change_entitlements")

# The three commands, and how each is named to the member in the question.
CHANGE_TYPES = ("stop_renewal", "pause", "cancel_now")
CHANGE_LABELS = {
    "stop_renewal": "stop the renewal, not an immediate cancellation",
    "pause": "pause it, not a cancellation",
    "cancel_now": "cancel now, so access ends today",
}
CHANGE_DONE = {"stop_renewal": "Renewal stopped", "pause": "Paused", "cancel_now": "Cancelled now"}

# Organisation fields the allowlist checks, wherever they appear in the fixture.
ORGANISATION_KEYS = ("organisation", "retailer", "company", "vendor", "merchant", "brand")


class FictionalOrganisationError(RuntimeError):
    """The fixture does not describe the casebook's fictional organisation."""


def _walk(value: Any):
    if isinstance(value, dict):
        for key, inner in value.items():
            yield key, inner
            yield from _walk(inner)
    elif isinstance(value, list):
        for inner in value:
            yield from _walk(inner)


def allowed_organisations(contract: dict) -> frozenset[str]:
    """The only organisation names the fixture may use: the contract's own."""
    return frozenset({contract["organisation"]})


def assert_fictional(data: dict, contract: dict) -> None:
    """Refuse fixture data whose organisations are not the casebook's fictional one.

    An allowlist, not a list of real names: every organisation field must read
    ``<allowed name> (fictional ...)``.
    """
    allowed = allowed_organisations(contract)
    found = [(k, v) for k, v in _walk(data) if k in ORGANISATION_KEYS]
    if not any(k == "organisation" for k, _ in found):
        raise FictionalOrganisationError("the fixture must name its organisation")
    for key, value in found:
        text = str(value or "")
        name, _, rest = text.partition(" (")
        if name not in allowed:
            raise FictionalOrganisationError(f"{key} {name!r} is not the casebook's organisation {sorted(allowed)}")
        if not rest.lower().startswith("fictional"):
            raise FictionalOrganisationError(f"{key} must be marked '(fictional ...)': {text!r}")
    if "fictional" not in str(data.get("note") or "").lower():
        raise FictionalOrganisationError("the fixture note must say the data is fictional")


# Read once, at import. Mantle imports lib/ from a temporary snapshot that is
# removed after loading, so a file read at dispatch time would fail.
_CONTRACT = json.loads(CONTRACT_FILE.read_text(encoding="utf-8"))
_DATA = json.loads(DATA_FILE.read_text(encoding="utf-8"))
assert_fictional(_DATA, _CONTRACT)

ORGANISATION = _DATA["organisation"].split(" (")[0]
SESSION_MEMBER_ID = _DATA["session_member_id"]


def load_contract() -> dict:
    return copy.deepcopy(_CONTRACT)


def load_data() -> dict:
    return copy.deepcopy(_DATA)


def rules(phase: str, contract: Optional[dict] = None) -> list[dict]:
    contract = contract or _CONTRACT
    return [rule for rule in contract["rules"] if rule["phase"] == phase]


def evaluate(facts: dict, phase: str, contract: Optional[dict] = None) -> Optional[str]:
    """First failing rule's reason for *phase*, or None. Exactly ``True`` passes."""
    for rule in rules(phase, contract):
        if facts.get(rule["field"]) is not True:
            return rule["reason"]
    return None


# ----------------------------------------------------------------------------
# Words: dates and amounts the agent must not invent (hooks.py, case metric)
# ----------------------------------------------------------------------------

# GPT-5.5 writes typographic apostrophes ("can\u2019t"). Every hedge below is
# written with a straight one, so text is normalised first (found in the
# Amber Grid payment-plan build, where the guard misread a refusal).
_APOSTROPHES = str.maketrans({"\u2019": "'", "\u2018": "'", "\u02bc": "'"})


def plain(text: str) -> str:
    return (text or "").translate(_APOSTROPHES)


_MONTHS = {
    "january": 1, "jan": 1, "february": 2, "feb": 2, "march": 3, "mar": 3, "april": 4, "apr": 4, "may": 5,
    "june": 6, "jun": 6, "july": 7, "jul": 7, "august": 8, "aug": 8, "september": 9, "sept": 9, "sep": 9,
    "october": 10, "oct": 10, "november": 11, "nov": 11, "december": 12, "dec": 12,
}
_MONTH = r"(" + "|".join(sorted(_MONTHS, key=len, reverse=True)) + r")\.?"
ISO_DATE_RE = re.compile(r"\b(20\d\d)-(\d\d)-(\d\d)\b")
_NAMED_DATE_RE = re.compile(
    rf"\b{_MONTH}\s+(\d{{1,2}})(?:st|nd|rd|th)?\b(?:,?\s+(20\d\d)\b)?"
    rf"|\b(\d{{1,2}})(?:st|nd|rd|th)?\s+(?:of\s+)?{_MONTH}(?:,?\s+(20\d\d)\b)?",
    re.IGNORECASE,
)
_NUMERIC_DATE_RE = re.compile(r"\b(\d{1,2})/(\d{1,2})/(20\d\d)\b")  # US month/day/year
AMOUNT_RE = re.compile(r"\$\s?(\d{1,5}(?:,\d{3})*(?:\.\d{1,2})?)")
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")
# Commas and colons split only before a space, so "$1,200" and "00:00" stay whole.
_CLAUSE_RE = re.compile(r",\s+|;\s*|:\s+|\s+but\s+|\s+-\s+|\s+—\s+")
# A clause that refuses, conditions or reports someone else's figure is not a
# disclosure: "I can't pause it until March 1", "the date you mentioned".
_CLAUSE_HEDGE_RE = re.compile(
    r"\b(?:not|no|never|cannot|can't|won't|isn't|wasn't|aren't|don't|doesn't|unable|asked|requested|mentioned"
    r"|wanted|suggested|instead\s+of|rather\s+than|if|whether|unless)\b|n't\b",
    re.IGNORECASE,
)


def dates_in(text: str) -> list[tuple[Optional[int], int, int, str]]:
    """(year or None, month, day, raw) for every calendar date written in *text*."""
    found = []
    for m in ISO_DATE_RE.finditer(text):
        found.append((int(m.group(1)), int(m.group(2)), int(m.group(3)), m.group(0)))
    for m in _NAMED_DATE_RE.finditer(text):
        if m.group(1):
            month, day, year = _MONTHS[m.group(1).lower()], int(m.group(2)), m.group(3)
        else:
            month, day, year = _MONTHS[m.group(5).lower()], int(m.group(4)), m.group(6)
        if 1 <= day <= 31:
            found.append((int(year) if year else None, month, day, m.group(0)))
    for m in _NUMERIC_DATE_RE.finditer(text):
        month, day = int(m.group(1)), int(m.group(2))
        if 1 <= month <= 12 and 1 <= day <= 31:
            found.append((int(m.group(3)), month, day, m.group(0)))
    return found


def to_money(value: Any) -> Optional[Decimal]:
    try:
        return Decimal(str(value).replace(",", "").replace("$", "").strip()).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        return None


def known_figures(value: Any) -> tuple[set[tuple[int, int, int]], set[Decimal]]:
    """Every ISO date and dollar amount a tool result carries, anywhere in it."""
    text = value if isinstance(value, str) else json.dumps(value, default=str)
    dates = {(int(y), int(m), int(d)) for y, m, d in ISO_DATE_RE.findall(text)}
    amounts = {a for a in (to_money(x) for x in AMOUNT_RE.findall(text)) if a is not None}
    for key, inner in _walk(value if isinstance(value, (dict, list)) else {}):
        if isinstance(key, str) and key.endswith("_usd"):
            amount = to_money(inner)
            if amount is not None:
                amounts.add(amount)
    return dates, amounts


def unsupported_figures(text: str, dates: set[tuple[int, int, int]], amounts: set[Decimal]) -> list[str]:
    """Dates and amounts *text* puts forward that no tool result in the conversation carried."""
    found = []
    for sentence in _SENTENCE_RE.split(plain(text)):
        for clause in _CLAUSE_RE.split(sentence):
            if _CLAUSE_HEDGE_RE.search(clause):
                continue
            for year, month, day, raw in dates_in(clause):
                if not any(m == month and d == day and (year is None or y == year) for y, m, d in dates):
                    found.append(f"date {raw!r}")
            for raw in AMOUNT_RE.findall(clause):
                amount = to_money(raw)
                if amount is not None and amount not in amounts:
                    found.append(f"amount ${raw}")
    return found


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------


def _digest(*parts: Any) -> str:
    return hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()[:8].upper()


def _parse(ts: str) -> datetime:
    return datetime.fromisoformat(ts)


def effective_text(ts: str) -> str:
    """'2027-01-12T00:00:00+00:00' -> '2027-01-12 00:00 UTC' (the fixture clock is UTC)."""
    moment = _parse(ts)
    return f"{moment:%Y-%m-%d %H:%M} UTC"


def normalise_change_type(value: Any) -> Optional[str]:
    text = re.sub(r"[\s-]+", "_", str(value or "").strip().lower())
    return text if text in CHANGE_TYPES else None


def change_tag(sub_id: str, change_type: str, revision: int) -> str:
    return f"{sub_id} {change_type} r{revision}"


def parse_tag(tag: Optional[str]) -> tuple[Optional[str], Optional[str], Optional[int]]:
    match = re.fullmatch(r"\s*(WS-SUB-\d{4})\s+([a-z_]+)\s+r(\d+)\s*", str(tag or ""), re.IGNORECASE)
    if not match:
        return None, None, None
    return match.group(1).upper(), match.group(2).lower(), int(match.group(3))


def money(value: Any) -> str:
    amount = to_money(value)
    return f"{amount:,.2f}" if amount is not None else str(value)


def memory_values_fit(values: dict) -> bool:
    return all(len(str(v)) <= MEMORY_VALUE_LIMIT for v in values.values())


# ----------------------------------------------------------------------------
# The conversation, as the tools see it (built from tracker events)
# ----------------------------------------------------------------------------


@dataclass(frozen=True)
class Conversation:
    # Text of the latest bot message stamped with CONFIRM_UTTER, and whether a
    # member message came after it.
    confirmation_question: Optional[str] = None
    confirmation_answered: bool = False
    user_messages: tuple[str, ...] = field(default_factory=tuple)


# ----------------------------------------------------------------------------
# The subscription service (one per conversation)
# ----------------------------------------------------------------------------


class SubscriptionService:
    """Willow Shop's subscription service for one conversation.

    ``commands`` logs every command that reached the service, so a test (and
    the case metric) can count additional cancellations. ``response_filter``
    lets a test corrupt the service's answer to exercise the receipt rule.
    """

    def __init__(self, data: Optional[dict] = None) -> None:
        self.data = data or load_data()
        self.as_of = _parse(self.data["as_of"])
        self.members: dict[str, dict] = self.data["members"]
        self.subs: dict[str, dict] = self.data["subscriptions"]
        self.commands: list[dict] = []  # every command sent, in order
        self.applied: dict[str, dict] = {}  # request key -> the service's own record
        self.pending: dict[str, dict] = {}  # sub id -> request awaiting verification
        self.changes: dict[str, dict] = {}  # sub id -> verified change
        self.referrals: dict[str, dict] = {}
        self.updated: set[str] = set()
        self.timed_out: set[str] = set()
        self.response_filter: Optional[Callable[[dict], Optional[dict]]] = None

    @property
    def today(self) -> str:
        return self.data["as_of"][:10]

    def member_subs(self, member_id: str) -> list[str]:
        return sorted(s for s, sub in self.subs.items() if sub["member_id"] == member_id)

    def option(self, sub_id: str, change_type: str) -> dict:
        return self.subs[sub_id]["options"][change_type]

    def touch(self, sub_id: str) -> Optional[str]:
        """Contact the service about *sub_id*. Applies a fixture's concurrent update once; returns why."""
        sub = self.subs[sub_id]
        update = sub.get("update_on_first_command")
        if not update or sub_id in self.updated:
            return None
        self.updated.add(sub_id)
        for key in ("revision", "paid_through", "next_charge", "options"):
            sub[key] = copy.deepcopy(update[key])
        return update["why"]

    def execute(self, sub_id: str, change_type: str, request_key: str) -> Optional[dict]:
        """Send one command. Returns the service's answer, or None when the result is unknown."""
        sub = self.subs[sub_id]
        option = self.option(sub_id, change_type)
        record = {
            "request_key": request_key,
            "subscription": sub_id,
            "command": change_type,
            "revision_before": sub["revision"],
            "revision_after": sub["revision"] + 1,
            "effective_at": option["effective_at"],
            "entitlements": option["entitlements"],
            "remaining": option["remaining"],
            "refund_usd": option["refund_usd"],
            "points_forfeited": option["points_forfeited"],
        }
        self.commands.append({"subscription": sub_id, "command": change_type, "request_key": request_key})
        self.applied[request_key] = record
        sub["revision"] += 1
        sub["state"] = {"stop_renewal": "renewal stopped", "pause": "paused", "cancel_now": "cancelled"}[change_type]
        if sub.get("command_response") == "timeout_then_applied" and sub_id not in self.timed_out:
            self.timed_out.add(sub_id)
            return None
        answer = copy.deepcopy(record)
        return self.response_filter(answer) if self.response_filter else answer

    def lookup(self, request_key: str, original_revision: int) -> Optional[dict]:
        """The service's record for a request key and the revision it was sent against. Changes nothing."""
        record = self.applied.get(request_key)
        if record is None or record["revision_before"] != original_revision:
            return None
        return copy.deepcopy(record)


_SERVICES: dict[str, SubscriptionService] = {}


def service_for(conversation_id: str) -> SubscriptionService:
    """One service per conversation, so every scripted conversation starts from the same data."""
    if conversation_id not in _SERVICES:
        _SERVICES[conversation_id] = SubscriptionService()
    return _SERVICES[conversation_id]


def member_profile(service: SubscriptionService, member_id: Optional[str] = None) -> dict:
    member_id = member_id or SESSION_MEMBER_ID
    person = service.members[member_id]
    subs = service.member_subs(member_id)
    return {
        "member_id": member_id,
        "first_name": person["first_name"],
        "subscription_list": "; ".join(service.subs[s]["label"] for s in subs),
    }


# ----------------------------------------------------------------------------
# Which subscription
# ----------------------------------------------------------------------------


def _label(service: SubscriptionService, sub_id: str) -> str:
    return f"{service.subs[sub_id]['label']} ({sub_id})"


def resolve_subscription(service: SubscriptionService, member_id: str, words: str) -> tuple[Optional[str], dict]:
    """The member's own subscription from their words or its number, or a blocked result.

    Another member's subscription number gets the same answer as a number that
    does not exist, so the agent cannot confirm whose it is.
    """
    text = str(words or "").strip()
    mine = service.member_subs(member_id)
    number = re.search(r"\b(?:WS[-\s]?SUB[-\s]?)?(\d{4})\b", text, re.IGNORECASE)
    if number:
        sub_id = f"WS-SUB-{number.group(1)}"
        if sub_id in mine:
            return sub_id, {}
        return None, {
            "status": "not_found",
            "reason": "no_such_subscription",
            "next_step": "Say there is no subscription with that number on their Willow Shop login; name their own.",
            "your_subscriptions": [_label(service, s) for s in mine],
        }
    lowered = plain(text).lower()
    candidates = [s for s in mine
                  if any(re.search(rf"\b{re.escape(a)}\b", lowered) for a in service.subs[s]["aliases"])
                  or service.subs[s]["label"].lower() in lowered]
    if len(candidates) == 1:
        return candidates[0], {}
    return None, {
        "status": "blocked",
        "reason": "which_subscription",
        "next_step": "Ask which subscription they mean; name the candidates.",
        "candidates": [_label(service, s) for s in (candidates or mine)],
    }


def _summary(service: SubscriptionService, sub_id: str) -> dict:
    sub = service.subs[sub_id]
    return {
        "subscription": sub_id,
        "subscription_label": sub["label"],
        "revision": sub["revision"],
        "billing": sub["billing"],
        "price_usd": sub["price_usd"],
        "paid_through": sub["paid_through"],
        "next_charge": sub["next_charge"],
        "benefits": sub["benefits"],
        "state": sub.get("state", "active, renews automatically"),
    }


def _option_view(service: SubscriptionService, sub_id: str, change_type: str) -> dict:
    option = service.option(sub_id, change_type)
    return {
        "change_type": change_type,
        "change_label": CHANGE_LABELS[change_type],
        "effective": effective_text(option["effective_at"]),
        "entitlements": option["entitlements"],
        "remaining": option["remaining"],
        "refund_usd": option["refund_usd"],
        "points_forfeited": option["points_forfeited"],
    }


# ----------------------------------------------------------------------------
# Tools' logic
# ----------------------------------------------------------------------------


def list_subscriptions(service: SubscriptionService, member_id: str) -> dict:
    person = service.members[member_id]
    return {
        "status": "ok",
        "today": service.today,
        "points_balance": person["points_balance"],
        "plus_bonus_points": person["plus_bonus_points"],
        "subscriptions": [_summary(service, s) for s in service.member_subs(member_id)],
        "next_step": "Changes nothing. To change one, compare its options first.",
    }


def compare_subscription_changes(service: SubscriptionService, member_id: str, words: str) -> dict:
    """What stopping renewal, pausing and cancelling now would each do to one subscription. Changes nothing."""
    sub_id, blocked = resolve_subscription(service, member_id, words)
    if sub_id is None:
        return blocked
    result = {"status": "options", "today": service.today, **_summary(service, sub_id),
              "options": [_option_view(service, sub_id, t) for t in CHANGE_TYPES]}
    if sub_id in service.changes:
        result["recorded_change"] = {k: service.changes[sub_id][k] for k in ("change_reference", "change_type")}
        result["next_step"] = "A change is already recorded on this subscription; use route_subscription_support."
    elif sub_id in service.pending:
        result["next_step"] = "A change request is pending. Call check_change_status; do not send another change."
    else:
        result["next_step"] = ("If the member has not said which change they want, tell them each option's effective "
                               "date and what they keep or lose, and ask which one. Never pick for them.")
    return result


def select_subscription_change(service: SubscriptionService, member_id: str, words: str,
                               change_type: str) -> tuple[dict, dict]:
    """(result, memory values). Selects one change so the engine can read its effect back."""
    clear = {key: "" for key in MEMORY_KEYS}
    sub_id, blocked = resolve_subscription(service, member_id, words)
    if sub_id is None:
        return blocked, clear
    kind = normalise_change_type(change_type)
    if kind is None:
        return {"status": "blocked", "reason": "which_change", "subscription": sub_id,
                "next_step": ("change_type must be stop_renewal, pause or cancel_now. Ask the member which, with "
                              "the dates from compare_subscription_changes.")}, clear
    if sub_id in service.changes:
        change = service.changes[sub_id]
        return {"status": "blocked", "reason": "change_already_recorded", "subscription": sub_id,
                "change_reference": change["change_reference"], "change_type": change["change_type"],
                "next_step": "One change per subscription in this chat. Offer route_subscription_support."}, clear
    if sub_id in service.pending:
        return {"status": "blocked", "reason": "change_pending", "subscription": sub_id,
                "next_step": "A change request is pending. Call check_change_status; do not send another."}, clear
    sub = service.subs[sub_id]
    option = service.option(sub_id, kind)
    memory = {
        "change_subscription": _label(service, sub_id),
        "change_tag": change_tag(sub_id, kind, sub["revision"]),
        "change_label": CHANGE_LABELS[kind],
        "change_effective": effective_text(option["effective_at"]),
        "change_entitlements": option["entitlements"],
    }
    return {
        "status": "selected",
        "subscription": sub_id,
        "subscription_label": sub["label"],
        "change_tag": memory["change_tag"],
        **_option_view(service, sub_id, kind),
        "next_step": ("Call apply_subscription_change with this subscription and change_type now; the engine reads "
                      "the effect back and asks the member."),
    }, memory


def change_facts(service: SubscriptionService, member_id: str, memory: dict, conversation: Conversation,
                 sub_id: str, change_type: Optional[str]) -> dict:
    """The contract's two request facts, from trusted data and events only."""
    tag_sub, tag_type, tag_rev = parse_tag(memory.get("change_tag"))
    sub = service.subs.get(sub_id)
    question = conversation.confirmation_question or ""
    label = str(memory.get("change_label") or "")
    effective = str(memory.get("change_effective") or "")
    entitlements = str(memory.get("change_entitlements") or "")
    asked = (
        conversation.confirmation_answered
        and bool(memory.get("change_tag"))
        and memory["change_tag"] in question
    )
    type_confirmed = (
        sub is not None
        and change_type is not None
        and tag_sub == sub_id
        and tag_type == change_type
        and label == CHANGE_LABELS[change_type]
        and asked
        and label in question
    )
    disclosed = False
    if sub is not None and change_type is not None:
        option = service.option(sub_id, change_type)
        disclosed = (
            tag_rev == sub["revision"]
            and effective == effective_text(option["effective_at"])
            and entitlements == option["entitlements"]
            and asked
            and effective in question
            and entitlements in question
        )
    return {"change_type_confirmed": type_confirmed, "entitlement_delta_disclosed": disclosed}


def receipt_facts(answer: Optional[dict], sub_id: str, change_type: str, disclosed: dict) -> dict:
    """The contract's receipt fact: the service's answer matches the command and the disclosed effect."""
    verified = (
        isinstance(answer, dict)
        and answer.get("subscription") == sub_id
        and answer.get("command") == change_type
        and answer.get("effective_at") == disclosed["effective_at"]
        and answer.get("entitlements") == disclosed["entitlements"]
    )
    return {"change_receipt_verified": verified}


def _record_change(service: SubscriptionService, sub_id: str, change_type: str, answer: dict, tag: str,
                   conversation_id: str, via: str) -> dict:
    change = {
        "change_reference": f"WS-CHG-{_digest(conversation_id, answer['request_key'])[:6]}",
        "subscription": sub_id,
        "subscription_label": service.subs[sub_id]["label"],
        "change_type": change_type,
        "change_tag": tag,
        "effective": effective_text(answer["effective_at"]),
        "entitlements": answer["entitlements"],
        "remaining": answer["remaining"],
        "refund_usd": answer["refund_usd"],
        "points_forfeited": answer["points_forfeited"],
        "request_key": answer["request_key"],
        "verified_by": via,
    }
    service.changes[sub_id] = change
    service.pending.pop(sub_id, None)
    return change


def apply_subscription_change(service: SubscriptionService, member_id: str, memory: dict,
                              conversation: Conversation, words: str, change_type: str,
                              conversation_id: str) -> dict:
    """Run one confirmed change: stop renewal, pause or cancel now."""
    sub_id, blocked = resolve_subscription(service, member_id, words)
    if sub_id is None:
        return {**blocked, "effects": 0}
    kind = normalise_change_type(change_type)
    tag_now = memory.get("change_tag") or ""
    if sub_id in service.changes:
        change = service.changes[sub_id]
        if kind == change["change_type"] and tag_now == change["change_tag"]:
            return {**change, "status": "succeeded", "replay": True, "effects": 0,
                    "next_step": "Already done; nothing was sent twice. Give the same change reference."}
        return {"status": "blocked", "reason": "change_already_recorded", "subscription": sub_id,
                "change_reference": change["change_reference"], "effects": 0,
                "next_step": "One change per subscription in this chat. Offer route_subscription_support."}
    if sub_id in service.pending:
        return {"status": "blocked", "reason": "change_pending", "subscription": sub_id, "effects": 0,
                "request_key": service.pending[sub_id]["request_key"],
                "next_step": ("A change request is already with the subscription service and its result is unknown. "
                              "Do not send another. Call check_change_status.")}
    why = service.touch(sub_id)
    facts = change_facts(service, member_id, memory, conversation, sub_id, kind)
    reason = evaluate(facts, "request")
    if reason:
        result = {"status": "blocked", "reason": reason, "subscription": sub_id, "change_type": kind,
                  "effects": 0, "facts": facts}
        if reason == "wrong_subscription_change":
            result["next_step"] = ("The member did not confirm this change type. Call select_subscription_change "
                                   "for the change they asked for, then apply_subscription_change so the engine asks.")
        else:
            result["next_step"] = ("The member was not told the current effect of this change. Call "
                                   "select_subscription_change again and tell them the new effective date and "
                                   "entitlements; apply only after they agree.")
            if kind is not None:
                result["current"] = _option_view(service, sub_id, kind)
            if why:
                result["why"] = why
        return result
    option = service.option(sub_id, kind)
    disclosed = {"effective_at": option["effective_at"], "entitlements": option["entitlements"]}
    request_key = f"RK-{_digest(conversation_id, tag_now)}"
    original_revision = service.subs[sub_id]["revision"]
    answer = service.execute(sub_id, kind, request_key)
    reason = evaluate(receipt_facts(answer, sub_id, kind, disclosed), "receipt")
    if reason:
        service.pending[sub_id] = {"request_key": request_key, "original_revision": original_revision,
                                   "change_type": kind, "change_tag": tag_now, "disclosed": disclosed}
        return {
            "status": "pending",
            "reason": reason,
            "subscription": sub_id,
            "change_type": kind,
            "request_key": request_key,
            "original_revision": original_revision,
            "effects": 1,
            "next_step": ("The change was sent but the subscription service has not confirmed it. Do not send it "
                          "again and do not say it is done. Call check_change_status now."),
        }
    change = _record_change(service, sub_id, kind, answer, tag_now, conversation_id, "command_answer")
    return {**change, "status": "succeeded", "replay": False, "effects": 1,
            "next_step": ("The member has been sent the change reference, effective time and what they keep. Add "
                          "only what they still need; do not repeat the reference.")}


def check_change_status(service: SubscriptionService, member_id: str, words: str, conversation_id: str) -> dict:
    """Recovery: read a pending change back by its request key and original revision. Sends no command."""
    sub_id, blocked = resolve_subscription(service, member_id, words)
    if sub_id is None:
        return blocked
    if sub_id in service.changes:
        return {**service.changes[sub_id], "status": "succeeded", "replay": True, "effects": 0,
                "next_step": "Already confirmed. Give the same change reference."}
    pending = service.pending.get(sub_id)
    if pending is None:
        return {"status": "no_change_requested", "subscription": sub_id, "effects": 0,
                "next_step": "No change was sent for this subscription in this chat."}
    record = service.lookup(pending["request_key"], pending["original_revision"])
    verified = receipt_facts(record, sub_id, pending["change_type"], pending["disclosed"])
    if evaluate(verified, "receipt"):
        return {"status": "pending", "reason": "change_not_recorded", "subscription": sub_id,
                "request_key": pending["request_key"], "original_revision": pending["original_revision"],
                "effects": 0,
                "next_step": ("The service has no confirmed record yet. Do not send the change again; offer "
                              "route_subscription_support.")}
    change = _record_change(service, sub_id, pending["change_type"], record, pending["change_tag"],
                            conversation_id, "status_check")
    return {**change, "status": "succeeded", "replay": False, "effects": 0,
            "original_revision": pending["original_revision"],
            "next_step": ("The earlier request went through; nothing was sent twice. The member has been sent the "
                          "change reference; do not repeat it.")}


def route_subscription_support(service: SubscriptionService, member_id: str, words: str, note: str,
                               conversation_id: str) -> dict:
    sub_id, blocked = resolve_subscription(service, member_id, words)
    if sub_id is None:
        return blocked
    key = f"support:{sub_id}"
    prior = service.referrals.get(key)
    replay = prior is not None
    if prior is None:
        prior = {
            "support_reference": f"WS-SUP-{_digest(conversation_id, key)[:6]}",
            "subscription": sub_id,
            "subscription_label": service.subs[sub_id]["label"],
            "team": "subscription support team",
            "note": str(note or "")[:300],
        }
        service.referrals[key] = prior
    return {"status": "routed", **prior, "replay": replay, "reply_within": "2 business days",
            "next_step": "Give the support reference. Nothing on the subscription has changed in this step."}


# ----------------------------------------------------------------------------
# The receipt the tool sends itself (TOOL_SENDS_RECEIPT)
# ----------------------------------------------------------------------------


def customer_receipt(tool: str, result: dict) -> Optional[str]:
    """The message a tool sends the member for an outcome they must see, or None.

    A replay sends nothing: the member already has the reference (the Amber
    Grid build re-sent a referral receipt on replay).
    """
    status = result.get("status")
    if result.get("replay"):
        return None
    if tool in ("apply_subscription_change", "check_change_status") and status == "succeeded":
        refund = to_money(result.get("refund_usd"))
        refund_text = f" Refund: ${money(refund)}." if refund else " No refund."
        return (f"Subscription change recorded: {result['change_reference']} for your "
                f"{result['subscription_label']} ({result['subscription']}). {CHANGE_DONE[result['change_type']]}, "
                f"effective {result['effective']}. After this change: {result['remaining']}.{refund_text}")
    if tool == "route_subscription_support" and status == "routed":
        return (f"Passed to the Willow Shop subscription support team: {result['support_reference']}, for your "
                f"{result['subscription_label']}. They reply within {result['reply_within']}. Nothing on the "
                "subscription has changed in this step.")
    return None
