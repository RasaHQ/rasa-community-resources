"""Horizon Rewards redemption service and the case guard, with no Rasa imports.

Everything here is fictional fixture data read from ``lib/fixtures/``. The guard
applies the three rules of the casebook contract for ``travel-redemption``
(vendored as ``lib/fixtures/case-contract.json``):

- ``member_account_verified`` (request): the points come from a rewards
  account that belongs to the member bound to this session and whose identity
  check is complete. Another member's account, an unknown number and the
  member's own unverified account all fail.
- ``reward_inventory_held`` (request): the redemption names an active hold on
  the reward's inventory, owned by this member, and it is the hold the engine
  asked the member to confirm. No hold, a released or expired hold, or a hold
  other than the confirmed one fails.
- ``redemption_commit_reconciled`` (receipt): after the commit, the points
  ledger entry and the booking record are read back and match: the debit
  equals the held points, and the booking is ticketed or confirmed for the
  same hold. When they do not match the redemption is ``pending`` with both
  states and an unresolved reversal, never ``succeeded``.

Facts are computed here from trusted data and session state. The model
supplies an account number as the member said it, a reward option id, a hold
id or a redemption reference copied from a tool result. It never supplies a
fact, a member id or an outcome. A fact that is not exactly ``True`` fails its
rule, as in the lab's ``evaluate``.

Two more rules come from the case text rather than its three predicates:

- A member holds one reward at a time. Switching means releasing the prior
  hold first (the case's correction), so a switched-away hold can never be
  spent and the confirmation always reads the current points.
- After a mismatch, the same reward cannot be held or redeemed again until
  the rewards desk has reconciled the existing records (the case's recovery),
  and a repeated commit on the same hold replays the stored result instead of
  debiting twice.

State lives in an in-process service with one copy of the fixture per
conversation, so every scripted conversation starts from the same balance.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

FIXTURES = Path(__file__).resolve().parent / "fixtures"
CONTRACT_FILE = FIXTURES / "case-contract.json"
DATA_FILE = FIXTURES / "horizon.json"

# Read once, at import. Mantle imports lib/ from a temporary snapshot that is
# removed after loading, so a file read at dispatch time would fail.
_CONTRACT = json.loads(CONTRACT_FILE.read_text(encoding="utf-8"))
_DATA = json.loads(DATA_FILE.read_text(encoding="utf-8"))

DEMO_MEMBER_ID = "HT-MEM-2044"
DESK = "Horizon Rewards desk"
BOOKED_STATES = ("ticketed", "confirmed")

_ID_RE = re.compile(r"[^A-Z0-9-]")


def load_contract() -> dict:
    return json.loads(json.dumps(_CONTRACT))


def load_data() -> dict:
    return json.loads(json.dumps(_DATA))


def rules(phase: str, contract: Optional[dict] = None) -> list[dict]:
    contract = contract or _CONTRACT
    return [rule for rule in contract["rules"] if rule["phase"] == phase]


def evaluate(facts: dict, phase: str, contract: Optional[dict] = None) -> Optional[str]:
    """First failing rule's reason for *phase*, or None. Exactly ``True`` passes."""
    for rule in rules(phase, contract):
        if facts.get(rule["field"]) is not True:
            return rule["reason"]
    return None


def _digest(*parts: str, size: int = 6) -> str:
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:size].upper()


def normalise_id(value: Any) -> str:
    """Upper-case, spaces to hyphens, drop anything else: ' rw lis 1014 ' -> RW-LIS-1014."""
    return _ID_RE.sub("", re.sub(r"\s+", "-", str(value or "").strip().upper()))


def normalise_account(value: Any) -> str:
    """'hr 204417', 'HR204417' and '204417' all become HR-204417."""
    raw = re.sub(r"[^A-Z0-9]", "", str(value or "").upper())
    if raw.startswith("HR"):
        raw = raw[2:]
    return f"HR-{raw}" if raw else ""


def points_text(points: int) -> str:
    return f"{points:,}"


class RewardsService:
    """The points ledger, reward inventory and bookings for one conversation."""

    def __init__(self, data: Optional[dict] = None) -> None:
        data = data or load_data()
        self.as_of = datetime.fromisoformat(data["as_of"])
        self.hold_minutes = data["hold_minutes"]
        self.members: dict[str, dict] = data["members"]
        self.accounts: dict[str, dict] = data["accounts"]
        self.options: dict[str, dict] = data["options"]
        self.holds: dict[str, dict] = data["holds"]
        self.redemptions: dict[str, dict] = data["redemptions"]
        self.ledger: list[dict] = []
        self.sequence = 0

    # -- trusted reads -------------------------------------------------------

    def account_verified_for(self, member_id: Optional[str], account: str) -> bool:
        record = self.accounts.get(account)
        return (
            bool(member_id)
            and record is not None
            and record["member_id"] == member_id
            and record["verification"] == "verified"
        )

    def own_unverified(self, member_id: Optional[str], account: str) -> bool:
        record = self.accounts.get(account)
        return bool(member_id) and record is not None and record["member_id"] == member_id \
            and record["verification"] != "verified"

    def accounts_of(self, member_id: Optional[str]) -> list[str]:
        return sorted(a for a, r in self.accounts.items() if member_id and r["member_id"] == member_id)

    def active_hold(self, account: str) -> Optional[dict]:
        for hold_id, hold in self.holds.items():
            if hold["rewards_account"] == account and hold["state"] == "active":
                return {"hold_id": hold_id, **hold}
        return None

    def reserved(self, account: str) -> int:
        hold = self.active_hold(account)
        return hold["points"] if hold else 0

    def open_mismatches(self, account: str, option_id: Optional[str] = None) -> list[str]:
        return sorted(
            ref for ref, r in self.redemptions.items()
            if r["rewards_account"] == account
            and r["status"] == "pending"
            and r["reversal"]["state"] != "reversed"
            and (option_id is None or r.get("option_id") == option_id)
        )

    def redemption_owned(self, member_id: Optional[str], reference: str) -> Optional[dict]:
        record = self.redemptions.get(reference)
        if record is None:
            return None
        owner = self.accounts.get(record["rewards_account"], {}).get("member_id")
        return record if member_id and owner == member_id else None

    def reward_label(self, record: dict) -> str:
        option = self.options.get(record.get("option_id") or "")
        return record.get("reward") or (option["label"] if option else "")

    def public_redemption(self, reference: str, record: dict) -> dict:
        return {
            "redemption_reference": reference,
            "status": record["status"],
            "reason": record["reason"],
            "rewards_account": record["rewards_account"],
            "option_id": record.get("option_id"),
            "reward": self.reward_label(record),
            "hold_id": record.get("hold_id"),
            "created_at": record.get("created_at"),
            "points": dict(record["points"]),
            "booking": dict(record["booking"]),
            "reversal": dict(record["reversal"]),
        }


_SERVICES: dict[str, RewardsService] = {}


def service_for(conversation_id: str) -> RewardsService:
    if conversation_id not in _SERVICES:
        _SERVICES[conversation_id] = RewardsService()
    return _SERVICES[conversation_id]


# ----------------------------------------------------------------------------
# Tool logic
# ----------------------------------------------------------------------------

WRONG_ACCOUNT_STEP = (
    "Say you cannot use that rewards account in this chat and ask the member to "
    "check the number. Points can only come from the member's own verified "
    "account. Do not say whether the number exists or whose it is."
)
UNVERIFIED_ACCOUNT_STEP = (
    "This is the member's own account, but its identity check is not complete, "
    "so its points cannot be redeemed here. The Horizon Rewards desk completes "
    "the check. Offer to use their verified account instead."
)


def _blocked(reason: str, next_step: str, **extra: Any) -> dict:
    return {"status": "blocked", "reason": reason, **extra, "effects": 0, "next_step": next_step}


def _wrong_account(service: RewardsService, member_id: Optional[str], account: str, **extra: Any) -> dict:
    # Someone else's account and an unknown number get the same payload, so the
    # answer never confirms that a number exists for another member.
    step = UNVERIFIED_ACCOUNT_STEP if service.own_unverified(member_id, account) else WRONG_ACCOUNT_STEP
    return _blocked(
        "wrong_rewards_account", step, rewards_account=account,
        facts={"member_account_verified": False}, **extra,
    )


def member_profile(service: RewardsService, member_id: str = DEMO_MEMBER_ID) -> dict:
    person = service.members[member_id]
    verified = [a for a in service.accounts_of(member_id) if service.account_verified_for(member_id, a)]
    return {
        "member_id": member_id,
        "first_name": person["first_name"],
        "last_name": person["last_name"],
        "rewards_account": verified[0] if verified else "",
    }


def points_balance(service: RewardsService, member_id: Optional[str], rewards_account: str) -> dict:
    account = normalise_account(rewards_account)
    if not service.account_verified_for(member_id, account):
        return _wrong_account(service, member_id, account)
    record = service.accounts[account]
    reserved = service.reserved(account)
    mismatches = [
        {
            "redemption_reference": ref,
            "reward": service.reward_label(service.redemptions[ref]),
            "points": dict(service.redemptions[ref]["points"]),
            "booking_state": service.redemptions[ref]["booking"]["state"],
            "reversal": dict(service.redemptions[ref]["reversal"]),
        }
        for ref in service.open_mismatches(account)
    ]
    result = {
        "status": "answered",
        "rewards_account": account,
        "points_balance": record["points_balance"],
        "points_reserved_by_hold": reserved,
        "points_available": record["points_balance"] - reserved,
        "as_of": service.as_of.isoformat(),
        "open_mismatches": mismatches,
        "next_step": "Report the balance and what is reserved.",
    }
    if mismatches:
        result["next_step"] = (
            "Report the balance. Also say that the listed redemption took points "
            "without a booking and is not reconciled; the balance already has "
            "those points taken off. Offer request_rewards_desk_review for it."
        )
    return result


def search_options(service: RewardsService, destination: str, travel_date: Optional[str] = None) -> dict:
    """Options matching a destination (and date). A search result is not a hold."""
    words = str(destination or "").strip().lower()
    date = str(travel_date or "").strip()[:10]
    found = []
    for option_id, option in sorted(service.options.items()):
        if not any(term in words or words in term for term in option["search_terms"]) or not words:
            continue
        if date and option["travel_date"] != date:
            continue
        found.append({
            "option_id": option_id,
            "reward": option["label"],
            "kind": option["kind"],
            "points": option["points"],
            "shown_available": option["inventory"],
        })
    if not found:
        return {
            "status": "no_options",
            "destination": destination,
            "travel_date": date or None,
            "next_step": "Say nothing matched and ask for another destination or date.",
        }
    return {
        "status": "found",
        "options": found,
        "note": "Search results are not holds. Inventory can change until hold_reward succeeds.",
        "next_step": (
            "Offer the options with their points. When the member picks one, call "
            "hold_reward with its option_id."
        ),
    }


def hold_reward(
    service: RewardsService,
    member_id: Optional[str],
    rewards_account: str,
    option_id: str,
    conversation_id: str,
) -> dict:
    """Reserve the reward's inventory and the points together, or neither."""
    account = normalise_account(rewards_account)
    ref = normalise_id(option_id)
    if not service.account_verified_for(member_id, account):
        return _wrong_account(service, member_id, account, option_id=ref)
    option = service.options.get(ref)
    if option is None:
        return {
            "status": "not_found",
            "option_id": ref,
            "next_step": "No reward has that id. Search again and use an option_id from the results.",
        }
    open_refs = service.open_mismatches(account, ref)
    if open_refs:
        return _blocked(
            "points_booking_mismatch",
            (
                "An earlier redemption of this same reward took points without a "
                "booking and is not reconciled. Do not hold or redeem this reward "
                "again. Give the member the reference and call "
                "request_rewards_desk_review for it."
            ),
            option_id=ref,
            open_redemption_reference=open_refs[0],
        )
    active = service.active_hold(account)
    if active is not None:
        return _blocked(
            "active_hold_exists",
            (
                "One reward can be held at a time. If the member is switching to "
                "this reward, call release_hold for the active hold first, then "
                "hold this one. If they want both, complete or release the active "
                "hold first."
            ),
            option_id=ref,
            active_hold={
                "hold_id": active["hold_id"],
                "reward": service.options[active["option_id"]]["label"],
                "points": active["points"],
            },
        )
    if option.get("gone_before_hold"):
        option["inventory"] = 0
    if option["inventory"] <= 0:
        return {
            "status": "unavailable",
            "reason": "reward_inventory_gone",
            "option_id": ref,
            "reward": option["label"],
            "detail": option.get("gone_detail", "No inventory is left for this reward."),
            "points_reserved": 0,
            "effects": 0,
            "next_step": (
                "Nothing is held and no points were reserved or taken. Say the "
                "reward is no longer available and offer other options. Do not "
                "redeem it."
            ),
        }
    available = service.accounts[account]["points_balance"] - service.reserved(account)
    if option["points"] > available:
        return {
            "status": "unavailable",
            "reason": "insufficient_points",
            "option_id": ref,
            "reward": option["label"],
            "points_needed": option["points"],
            "points_available": available,
            "effects": 0,
            "next_step": (
                "Nothing is held. Points cannot be combined with or borrowed from "
                "another member's account. Offer an option within the balance."
            ),
        }
    service.sequence += 1
    hold_id = f"HT-H-{_digest(conversation_id, ref, str(service.sequence), size=5)}"
    expires = service.as_of + timedelta(minutes=service.hold_minutes)
    option["inventory"] -= 1
    service.holds[hold_id] = {
        "rewards_account": account,
        "member_id": member_id,
        "option_id": ref,
        "points": option["points"],
        "state": "active",
        "held_at": service.as_of.isoformat(),
        "expires_at": expires.isoformat(),
    }
    return {
        "status": "held",
        "hold_id": hold_id,
        "option_id": ref,
        "reward": option["label"],
        "points": option["points"],
        "rewards_account": account,
        "points_balance": service.accounts[account]["points_balance"],
        "points_available_after_hold": available - option["points"],
        "expires_at": expires.isoformat(),
        "facts": {"member_account_verified": True, "reward_inventory_held": True},
        "next_step": (
            "In this same turn, call redeem_reward with this hold_id. That call "
            "is what shows the member the confirmation question with the reward "
            "and the points; no points move until they confirm. Do not end your "
            "turn after the hold and do not ask a confirmation question of your own."
        ),
    }


def release_hold(service: RewardsService, member_id: Optional[str], hold_id: str) -> dict:
    ref = normalise_id(hold_id)
    hold = service.holds.get(ref)
    if hold is None or hold["member_id"] != member_id:
        return {"status": "not_found", "hold_id": ref, "next_step": "No hold with that id on this member's account."}
    if hold["state"] != "active":
        return {
            "status": "not_active",
            "hold_id": ref,
            "state": hold["state"],
            "next_step": "That hold is not active, so there is nothing to release.",
        }
    hold["state"] = "released"
    service.options[hold["option_id"]]["inventory"] += 1
    account = hold["rewards_account"]
    return {
        "status": "released",
        "hold_id": ref,
        "option_id": hold["option_id"],
        "reward": service.options[hold["option_id"]]["label"],
        "points_released": hold["points"],
        "points_available": service.accounts[account]["points_balance"] - service.reserved(account),
        "effects": 0,
        "next_step": (
            "Nothing was redeemed for this hold. If the member chose another "
            "reward, call hold_reward for it and give its points."
        ),
    }


def _commit_booking(option: dict) -> dict:
    """The booking system's answer for a committed redemption (fixture-driven)."""
    if option["fulfilment"] in BOOKED_STATES:
        return {"state": option["fulfilment"]}
    return {"state": "not_ticketed", "booking_reference": None, "detail": option.get("fulfilment_detail")}


def redeem_reward(
    service: RewardsService,
    member_id: Optional[str],
    session_account: Optional[str],
    confirmed_hold_id: Optional[str],
    hold_id: str,
    conversation_id: str,
) -> dict:
    """Commit one confirmed hold: debit the points, book the reward, reconcile both."""
    ref = normalise_id(hold_id)
    hold = service.holds.get(ref)
    if hold is not None and hold["member_id"] != member_id:
        hold = None
    if hold is not None and hold["state"] == "redeemed":
        # A repeated commit on the same hold returns the stored result: the
        # points are never debited twice for one hold.
        reference = hold["redemption_reference"]
        record = service.redemptions[reference]
        return {
            **service.public_redemption(reference, record),
            "effects": 0,
            "replay": True,
            "unmatched_points_booking": 0,
            "next_step": (
                "This hold was already redeemed; nothing new was taken. Report the "
                "stored points and booking state."
            ),
        }
    account = hold["rewards_account"] if hold is not None else normalise_account(session_account)
    facts = {
        "member_account_verified": service.account_verified_for(member_id, account),
        "reward_inventory_held": (
            hold is not None
            and hold["state"] == "active"
            and bool(confirmed_hold_id)
            and ref == normalise_id(confirmed_hold_id)
        ),
    }
    reason = evaluate(facts, "request")
    if reason == "wrong_rewards_account":
        return _wrong_account(service, member_id, account, hold_id=ref)
    if reason:
        return _blocked(
            reason,
            (
                "No points were taken. There is no active, confirmed hold with "
                "this id: it was never made, was released, expired, or is not the "
                "hold the member confirmed. Call hold_reward for the reward the "
                "member wants and redeem the new hold_id."
            ),
            hold_id=ref,
            hold_state=hold["state"] if hold is not None else None,
            facts=facts,
        )
    option_id = hold["option_id"]
    option = service.options[option_id]
    if service.open_mismatches(account, option_id):
        return _blocked(
            "points_booking_mismatch",
            "An earlier redemption of this reward is unreconciled. Do not redeem it again.",
            hold_id=ref,
            open_redemption_reference=service.open_mismatches(account, option_id)[0],
        )

    # Commit: the points ledger and the booking system are separate services.
    service.sequence += 1
    reference = f"HT-RD-{_digest(conversation_id, ref, size=5)}"
    ledger_entry = f"HR-LEDGER-{_digest(reference, 'debit', size=5)}"
    service.accounts[account]["points_balance"] -= hold["points"]
    service.ledger.append({"entry": ledger_entry, "hold_id": ref, "amount": hold["points"]})
    booking = _commit_booking(option)
    if booking["state"] in BOOKED_STATES:
        booking["booking_reference"] = f"HZ{_digest(reference, 'booking', size=5)}"
        booking["hold_id"] = ref
    else:
        # The seat never reached the member; the inventory hold lapses.
        option["inventory"] += 1
    hold["state"] = "redeemed"
    hold["redemption_reference"] = reference

    # Receipt: read both records back and compare them.
    debit = next(e for e in service.ledger if e["entry"] == ledger_entry)
    facts["redemption_commit_reconciled"] = (
        debit["amount"] == hold["points"]
        and booking["state"] in BOOKED_STATES
        and booking.get("hold_id") == debit["hold_id"] == ref
    )
    receipt_failure = evaluate(facts, "receipt")
    booking.pop("hold_id", None)
    record = {
        "status": "pending" if receipt_failure else "succeeded",
        "reason": receipt_failure or "verified_fixture_receipt",
        "rewards_account": account,
        "option_id": option_id,
        "hold_id": ref,
        "created_at": service.as_of.isoformat(),
        "points": {"state": "debited", "amount": hold["points"], "ledger_entry": ledger_entry},
        "booking": booking,
        "reversal": {"state": "unresolved" if receipt_failure else "not_needed", "owner": DESK},
    }
    service.redemptions[reference] = record
    result = {
        **service.public_redemption(reference, record),
        "points_balance_after": service.accounts[account]["points_balance"],
        "effects": 1,
        "replay": False,
        "unmatched_points_booking": 1 if receipt_failure else 0,
        "facts": facts,
    }
    if receipt_failure:
        result["next_step"] = (
            "The points were taken but the reward was not booked. Tell the member "
            "exactly that, with the redemption reference, the points state and the "
            "booking state. Stop: do not call redeem_reward or hold_reward again "
            "for this reward, and do not describe it as booked. Call "
            "request_rewards_desk_review with this redemption_reference; the "
            "rewards desk reverses inconsistent records."
        )
    else:
        result["next_step"] = (
            "Give the redemption reference, the points taken and the booking reference."
        )
    return result


def redemption_status(service: RewardsService, member_id: Optional[str], redemption_reference: str) -> dict:
    ref = normalise_id(redemption_reference)
    record = service.redemption_owned(member_id, ref)
    if record is None:
        # Unknown and another member's reference look the same.
        return {
            "status": "not_found",
            "redemption_reference": ref,
            "next_step": "Say you cannot find that reference on this member's account and ask them to check it.",
        }
    result = {"lookup": "found", **service.public_redemption(ref, record)}
    if record["status"] == "pending":
        result["next_step"] = (
            "Points were taken without a matching booking. Say so plainly with both "
            "states. Do not redeem this reward again. If the reversal is not yet "
            "requested, offer request_rewards_desk_review."
        )
    else:
        result["next_step"] = "Report the points taken and the booking reference."
    return result


def rewards_desk_review(service: RewardsService, member_id: Optional[str], redemption_reference: str, note: str = "") -> dict:
    ref = normalise_id(redemption_reference)
    record = service.redemption_owned(member_id, ref)
    if record is None:
        return {
            "status": "not_found",
            "redemption_reference": ref,
            "next_step": "Say you cannot find that reference on this member's account.",
        }
    if record["status"] != "pending":
        return {
            "status": "not_needed",
            "redemption_reference": ref,
            "next_step": "The points and the booking match; there is nothing to reverse.",
        }
    replay = "desk_case" in record["reversal"]
    case = record["reversal"].get("desk_case") or f"HT-DSK-{_digest(member_id or '', ref, size=5)}"
    record["reversal"] = {"state": "requested", "owner": DESK, "desk_case": case}
    return {
        "status": "routed",
        "desk_case": case,
        "redemption_reference": ref,
        "reward": service.reward_label(record),
        "points": dict(record["points"]),
        "booking": dict(record["booking"]),
        "reversal": dict(record["reversal"]),
        "replay": replay,
        "note": " ".join(str(note or "").split())[:300],
        "next_review_step": (
            "The Horizon Rewards desk reconciles the points ledger and the booking "
            "record within two business days. Until then the points are not "
            "returned and no seat or room is booked."
        ),
        "next_step": "Give the desk case and the next review step. Do not promise a refund date or a rebooking.",
    }
