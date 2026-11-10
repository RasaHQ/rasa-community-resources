"""Willow Shop order payments over voice and the case guard, with no Rasa imports.

Everything here is fictional fixture data read from ``lib/fixtures/``. The
guard applies the casebook contract for ``voice-payment-boundary`` (vendored
as ``lib/fixtures/case-contract.json``): two request rules and one receipt
rule.

- ``secure_channel_selected`` (request): the payment goes through an approved
  channel, a processor-hosted payment page sent as a link by text or email
  to the contact details already on the account. There is no tool, argument
  or channel that takes card details on the call. A channel the model names
  that is not approved ("phone", "over the call", "card") fails the rule, and
  so does any tool argument that carries card digits.
- ``recorder_excluded`` (request): card details are kept out of the
  conversation record. It holds only when the speech-to-text engine that
  removes card details from transcripts is running in this process
  (``engines/deepgram_pci.py`` sets ``REDACTION_FLAG``) and none of the
  caller's messages in the tracker still holds a card number, security code
  or expiry date. If either fails, the payment step does not start.
- ``processor_receipt_verified`` (receipt): the payment is paid only when the
  processor's receipt for this order and amount carries a signature that
  verifies. Anything else, including the caller saying they paid, leaves it
  pending.

Facts are computed here from trusted data and from the caller's own messages.
The model supplies an order number and a channel word. It never supplies a
fact, a customer id or a payment outcome, and nothing it passes is echoed back
if it looks like card data. A fact that is not exactly ``True`` fails its
rule, as in the lab's ``evaluate``.

Payment state (links, processor sessions) lives in an in-process service with
one copy of the fixture per conversation, so every scripted call starts from
the same orders. The processor is simulated: a session opened in one caller
turn reports its outcome from the next caller turn on, because a caller pays
on their phone between turns, never during one.

The organisation guard runs at import. It is an allowlist, not a list of real
names: the fixture's organisation must be exactly the casebook contract's
fictional organisation, marked ``(fictional)``, and the contract must be the
casebook's authored synthetic fixture.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
from pathlib import Path
from typing import Any, Iterable, Optional

from lib import pci

FIXTURES = Path(__file__).resolve().parent / "fixtures"
CONTRACT_FILE = FIXTURES / "case-contract.json"
DATA_FILE = FIXTURES / "orders.json"

# Set by engines/deepgram_pci.py when the redacting speech-to-text engine is
# created. Process-wide on purpose: it says this server's voice channel
# removes card details before Rasa records a transcript.
REDACTION_FLAG = "WILLOWSHOP_PCI_TRANSCRIPT_REDACTION"
REDACTION_VALUE = "on"

# Mantle cuts a memory value at 100 characters in the prompt without saying so
# (found in the GPT quote and diagnostics builds); every memory value is kept
# under this.
MEMORY_VALUE_LIMIT = 100
MEMORY_KEYS = ("pay_order", "pay_channel", "pay_order_label", "pay_channel_label")

# The tool sends the caller its own receipt through ToolContext.send (found in
# the claim-intake and collections builds: left to the model, references often
# never reach the customer).
TOOL_SENDS_RECEIPT = True


class FictionalOrganisationError(RuntimeError):
    """The fixture does not describe the casebook's fictional organisation."""


def assert_fictional(data: dict, contract: dict) -> None:
    """Refuse fixture data that is not the casebook's own fictional organisation.

    An allowlist: the only organisation accepted is the one the vendored
    casebook contract names, marked "(fictional)". No list of real names is
    kept anywhere in this project.
    """
    provenance = contract.get("provenance") or {}
    if provenance.get("kind") != "authored-synthetic-fixture":
        raise FictionalOrganisationError("the case contract must be the casebook's authored synthetic fixture")
    expected = f"{contract['organisation']} (fictional)"
    if data.get("organisation") != expected:
        raise FictionalOrganisationError(
            f"organisation must be exactly {expected!r}, got {data.get('organisation')!r}")
    if "(fictional" not in str(data.get("processor") or ""):
        raise FictionalOrganisationError("the payment processor must be marked (fictional ...)")
    if "fictional" not in str(data.get("note") or "").lower():
        raise FictionalOrganisationError("the fixture note must say the data is fictional")
    for customer in data.get("customers", {}).values():
        if not str(customer.get("email", "")).endswith("@example.com"):
            raise FictionalOrganisationError("customer emails must use the reserved example.com domain")
        if " 555 01" not in str(customer.get("mobile", "")):
            raise FictionalOrganisationError("customer mobiles must be in the 555-01xx fictional range")


# Read once, at import. Mantle imports lib/ from a temporary snapshot that is
# removed after loading, so a file read at dispatch time would fail.
_CONTRACT = json.loads(CONTRACT_FILE.read_text(encoding="utf-8"))
_DATA = json.loads(DATA_FILE.read_text(encoding="utf-8"))
assert_fictional(_DATA, _CONTRACT)

ORGANISATION = _DATA["organisation"].split(" (")[0]
SESSION_CUSTOMER_ID = _DATA["session_customer_id"]
APPROVED_CHANNELS = tuple(_DATA["approved_channels"])
APPROVED_ALTERNATIVE = _DATA["approved_alternative"]


def load_contract() -> dict:
    return json.loads(json.dumps(_CONTRACT))


def load_data() -> dict:
    return json.loads(json.dumps(_DATA))


def rules(phase: str, contract: Optional[dict] = None) -> list[dict]:
    contract = contract or _CONTRACT
    return [rule for rule in contract["rules"] if rule["phase"] == phase]


def evaluate(facts: dict, phase: str = "request", contract: Optional[dict] = None) -> Optional[str]:
    """First failing rule's reason for the phase, or None. A fact must be exactly ``True``."""
    for rule in rules(phase, contract):
        if facts.get(rule["field"]) is not True:
            return rule["reason"]
    return None


def lab_outcome(facts: dict, contract: Optional[dict] = None) -> tuple[str, str, int]:
    """The lab's execute(): request rules block with no effect; the receipt rule leaves it pending."""
    reason = evaluate(facts, "request", contract)
    if reason:
        return "blocked", reason, 0
    reason = evaluate(facts, "receipt", contract)
    if reason:
        return "pending", reason, 1
    return "succeeded", "verified_fixture_receipt", 1


# ----------------------------------------------------------------------------
# Speech-friendly labels
# ----------------------------------------------------------------------------


def spoken_order(order: str) -> str:
    """'WS-10517' -> 'W S, 1 0 5 1 7': letters and digits one at a time."""
    prefix, _, digits = order.partition("-")
    return f"{' '.join(prefix)}, {' '.join(digits)}"


def spoken_reference(reference: str) -> str:
    """'QP-482913' -> 'Q P, 4 8 2, 9 1 3'."""
    prefix, _, digits = reference.partition("-")
    return f"{' '.join(prefix)}, {' '.join(digits[:3])}, {' '.join(digits[3:])}"


def spoken_amount(cents: int) -> str:
    dollars, rest = divmod(int(cents), 100)
    return f"{dollars} dollars" + (f" and {rest} cents" if rest else "")


def _mobile_ending(mobile: str) -> str:
    return " ".join(re.sub(r"\D", "", mobile)[-2:])


def channel_label(channel: str, customer: dict) -> str:
    if channel == "text":
        return f"by text to your mobile ending {_mobile_ending(customer['mobile'])}"
    return "by email to the address on your account"


# ----------------------------------------------------------------------------
# Normalising what the model passes
# ----------------------------------------------------------------------------

_TEXT_WORDS = ("text", "texts", "sms", "text message", "message", "txt", "texting")
_EMAIL_WORDS = ("email", "e-mail", "e mail", "mail", "emails", "inbox")


def normalise_channel(value: Any) -> Optional[str]:
    """'text' or 'email' for an approved channel, None for anything else."""
    text = re.sub(r"[_\s]+", " ", str(value or "").strip().lower())
    if text in _TEXT_WORDS or text.startswith(("text", "sms")):
        return "text"
    if text in _EMAIL_WORDS or text.startswith(("email", "e-mail")):
        return "email"
    return None


def normalise_order(value: Any) -> Optional[str]:
    """'WS-10517' for 'ws 10517', '10517' or 'W S one zero five one seven'; None otherwise."""
    digits = pci.digits_only(str(value or ""))
    if len(digits) != 5:
        return None
    return f"WS-{digits}"


def _carries_card_data(*values: Any) -> bool:
    return any(pci.contains_payment_secret(str(v)) for v in values if v is not None)


def redaction_active(environ: Optional[dict] = None) -> bool:
    return (environ if environ is not None else os.environ).get(REDACTION_FLAG) == REDACTION_VALUE


def record_holds_secret(user_texts: Iterable[str]) -> bool:
    return any(pci.contains_payment_secret(t) for t in user_texts)


# ----------------------------------------------------------------------------
# The payment service (one per conversation) and the simulated processor
# ----------------------------------------------------------------------------


def _reference(prefix: str, *parts: str) -> str:
    return f"{prefix}-{int(hashlib.sha256('|'.join(parts).encode()).hexdigest(), 16) % 1_000_000:06d}"


def _signature(reference: str, order: str, cents: int, status: str) -> str:
    key = _DATA["receipt_signing"]["fixture_key"].encode()
    return hmac.new(key, f"{reference}|{order}|{cents}|{status}".encode(), hashlib.sha256).hexdigest()


def verify_receipt(receipt: dict, order: str, cents: int) -> bool:
    """True only when the processor's receipt is for this order and amount and its signature verifies."""
    if receipt.get("order") != order or receipt.get("amount_cents") != cents:
        return False
    expected = _signature(receipt.get("reference", ""), order, cents, receipt.get("status", ""))
    return hmac.compare_digest(expected, str(receipt.get("signature", "")))


class PaymentService:
    """Orders, links and processor sessions for one conversation."""

    def __init__(self, conversation_id: str) -> None:
        self.conversation_id = conversation_id
        self.data = load_data()
        self.sessions: list[dict] = []
        self.pending_left: dict[str, dict] = {}

    def customer(self, customer_id: Optional[str]) -> Optional[dict]:
        return self.data["customers"].get(customer_id or "")

    def order(self, customer_id: Optional[str], order_number: Any) -> tuple[Optional[str], Optional[dict]]:
        order = normalise_order(order_number)
        record = self.data["orders"].get(order or "")
        if record is None or record["customer_id"] != customer_id:
            return order, None
        return order, record

    def open_session(self, order: str, channel: str, user_turn: int) -> Optional[dict]:
        record = self.data["orders"][order]
        script = record["processor"]
        if script.get("hosted_session_unavailable"):
            return None
        tries = [s for s in self.sessions if s["order"] == order]
        outcomes = script["sessions"]
        outcome = outcomes[min(len(tries), len(outcomes) - 1)] if outcomes else "open"
        session = {
            "session_id": _reference("PS", self.conversation_id, order, str(len(tries))),
            "order": order,
            "channel": channel,
            "amount_cents": record["balance_cents"],
            "opened_at_user_turn": user_turn,
            "outcome": outcome,
            "state": "open",
        }
        self.sessions.append(session)
        return session

    def latest_session(self, order: str) -> Optional[dict]:
        found = [s for s in self.sessions if s["order"] == order]
        return found[-1] if found else None

    def processor_report(self, session: dict, user_turn: int) -> dict:
        """What the processor says about a session, as the payment step would read it."""
        if user_turn <= session["opened_at_user_turn"] or session["outcome"] == "open":
            return {"session_id": session["session_id"], "state": "open"}
        if session["outcome"] == "expired":
            session["state"] = "expired"
            return {"session_id": session["session_id"], "state": "expired"}
        reference = _reference("QP", self.conversation_id, session["session_id"])
        receipt = {"reference": reference, "order": session["order"], "amount_cents": session["amount_cents"],
                   "status": "captured"}
        signature = _signature(reference, session["order"], session["amount_cents"], "captured")
        if session["outcome"] == "captured_unverified":
            signature = signature[::-1]  # the processor's receipt does not verify
        receipt["signature"] = signature
        session["state"] = "captured"
        return {"session_id": session["session_id"], "state": "captured", "receipt": receipt}


_SERVICES: dict[str, PaymentService] = {}


def service_for(conversation_id: str) -> PaymentService:
    if conversation_id not in _SERVICES:
        _SERVICES[conversation_id] = PaymentService(conversation_id)
    return _SERVICES[conversation_id]


# ----------------------------------------------------------------------------
# Tool logic
# ----------------------------------------------------------------------------


def _not_found(order: Optional[str]) -> dict:
    return {"status": "not_found", "order": order,
            "next_step": "Say you cannot find that order on this account and ask the caller to check the "
                         "order number. Never say whether it belongs to someone else."}


def look_up_order_balance(service: PaymentService, customer_id: Optional[str], order_number: Any) -> dict:
    if _carries_card_data(order_number):
        return _card_data_refusal()
    order, record = service.order(customer_id, order_number)
    if record is None:
        return _not_found(order)
    cents = record["balance_cents"]
    result = {
        "status": "balance_due" if cents else "paid_in_full",
        "order": order,
        "order_spoken": spoken_order(order),
        "summary": record["summary"],
        "balance_cents": cents,
        "balance_spoken": spoken_amount(cents),
        "approved_channels": list(APPROVED_CHANNELS),
    }
    if cents:
        result["hold_reason"] = record["hold_reason"]
        result["next_step"] = ("Offer the secure payment step: a link by text or email. Never take card "
                               "details on the call.")
    else:
        result["next_step"] = "Nothing is owed on this order; do not send a payment link."
    return result


def _card_data_refusal() -> dict:
    return {"status": "blocked", "reason": "unsafe_capture_channel", "effects": 0,
            "detail": "card_data_in_arguments",
            "next_step": "Card details are never taken on this call and were not kept. Ask the caller not to "
                         "read card details, and offer the secure payment link by text or email."}


def _request_facts(channel: Optional[str], user_texts: list[str], redaction_on: bool,
                   *arguments: Any) -> dict:
    return {
        "secure_channel_selected": channel in APPROVED_CHANNELS and not _carries_card_data(*arguments),
        "recorder_excluded": redaction_on and not record_holds_secret(user_texts),
    }


def _blocked(reason: str, order: Optional[str]) -> dict:
    if reason == "unsafe_capture_channel":
        step = ("Only a secure payment link by text or email is approved. Card details are never taken on "
                "this call. Offer the link, or the caller can " + APPROVED_ALTERNATIVE + ".")
    else:
        step = ("This call's record is not cleared for payment. Do not start a payment and do not ask the "
                "caller to repeat any card details. Tell them they can " + APPROVED_ALTERNATIVE + ".")
    return {"status": "blocked", "reason": reason, "effects": 0, "order": order, "next_step": step}


def prepare_secure_payment(service: PaymentService, customer_id: Optional[str], user_texts: list[str],
                           redaction_on: bool, order_number: Any, channel: Any) -> tuple[dict, dict]:
    """(result, memory values). Checks the request rules and sets up the read-back; sends nothing."""
    if _carries_card_data(order_number, channel):
        return _card_data_refusal(), {}
    order, record = service.order(customer_id, order_number)
    if record is None:
        return _not_found(order), {}
    if not record["balance_cents"]:
        return {"status": "nothing_owed", "order": order, "effects": 0,
                "next_step": "Nothing is owed on this order; do not send a payment link."}, {}
    chosen = normalise_channel(channel)
    facts = _request_facts(chosen, user_texts, redaction_on, order_number, channel)
    reason = evaluate(facts, "request")
    if reason:
        return {**_blocked(reason, order), "facts": facts}, {}
    unavailable = record["processor"].get("hosted_session_unavailable")
    if unavailable:
        return {
            "status": "cancelled", "reason": "secure_channel_unavailable", "effects": 0, "order": order,
            "detail": unavailable,
            "next_step": ("A secure payment link cannot be set up for this order, so collection is cancelled "
                          "on this call. Do not take card details and do not ask for them again. Tell the "
                          "caller they can " + APPROVED_ALTERNATIVE + ", where the partner seller's secure "
                          "page opens."),
        }, {}
    customer = service.customer(customer_id)
    memory = memory_values(order, chosen, record["balance_cents"], customer)
    return {"status": "ready", "order": order, "channel": chosen, "facts": facts, "effects": 0,
            "next_step": "Call send_secure_payment_link with this order straight away; the engine asks the "
                         "caller to confirm."}, memory


def memory_values(order: str, channel: str, cents: int, customer: dict) -> dict:
    values = {
        "pay_order": order,
        "pay_channel": channel,
        "pay_order_label": f"order {spoken_order(order)}, balance {spoken_amount(cents)}",
        "pay_channel_label": channel_label(channel, customer),
    }
    for key, value in values.items():
        if len(value) >= MEMORY_VALUE_LIMIT:
            raise ValueError(f"memory value {key} is {len(value)} characters; Mantle cuts at {MEMORY_VALUE_LIMIT}")
    return values


def send_secure_payment_link(service: PaymentService, customer_id: Optional[str], user_texts: list[str],
                             redaction_on: bool, memory: dict, order_number: Any, user_turn: int) -> dict:
    """Open a processor session and send its link, after the engine's confirmation."""
    if _carries_card_data(order_number):
        return _card_data_refusal()
    order, record = service.order(customer_id, order_number)
    if record is None:
        return _not_found(order)
    if memory.get("pay_order") != order:
        return {"status": "blocked", "reason": "unsafe_capture_channel", "effects": 0, "order": order,
                "detail": "not_prepared",
                "next_step": "Call prepare_secure_payment for this order and channel first."}
    channel = memory.get("pay_channel")
    facts = _request_facts(channel if channel in APPROVED_CHANNELS else None, user_texts, redaction_on,
                           order_number)
    reason = evaluate(facts, "request")
    if reason:
        return {**_blocked(reason, order), "facts": facts}
    session = service.open_session(order, channel, user_turn)
    if session is None:
        return {"status": "cancelled", "reason": "secure_channel_unavailable", "effects": 0, "order": order,
                "next_step": "Collection is cancelled. Tell the caller they can " + APPROVED_ALTERNATIVE + "."}
    customer = service.customer(customer_id)
    return {
        "status": "link_sent", "order": order, "channel": channel, "session_id": session["session_id"],
        "payment_status": "pending", "effects": 1, "facts": facts,
        "sent_to": channel_label(channel, customer),
        "next_step": ("The payment is pending until the processor confirms it. When the caller says they "
                      "have paid, call check_payment_status."),
    }


def check_payment_status(service: PaymentService, customer_id: Optional[str], order_number: Any,
                         user_turn: int) -> dict:
    if _carries_card_data(order_number):
        return _card_data_refusal()
    order, record = service.order(customer_id, order_number)
    if record is None:
        return _not_found(order)
    session = service.latest_session(order)
    if session is None:
        return {"status": "pending", "reason": "no_payment_session", "order": order, "effects": 0,
                "payment_status": "unpaid" if record["balance_cents"] else "paid_in_full",
                "next_step": ("No secure payment was started for this order on this call, so there is no "
                              "processor receipt. A payment the caller describes is not a receipt. Offer the "
                              "secure payment link.")}
    report = service.processor_report(session, user_turn)
    if report["state"] == "open":
        return {"status": "pending", "reason": "awaiting_customer", "order": order, "effects": 1,
                "payment_status": "pending", "session_id": session["session_id"],
                "next_step": "The processor has no payment yet. The caller can finish on the secure page."}
    if report["state"] == "expired":
        return {"status": "expired", "reason": "link_expired", "order": order, "effects": 0,
                "payment_status": "unpaid", "session_id": session["session_id"],
                "next_step": ("The link expired unpaid. Offer to send a new one: call prepare_secure_payment "
                              "again, then send_secure_payment_link.")}
    receipt = report["receipt"]
    facts = {"secure_channel_selected": True, "recorder_excluded": True,
             "processor_receipt_verified": verify_receipt(receipt, order, record["balance_cents"])}
    status, reason, effects = lab_outcome(facts)
    result = {"status": status, "reason": reason, "order": order, "effects": effects,
              "session_id": session["session_id"], "facts": facts}
    if status == "succeeded":
        result.update({"payment_status": "paid", "processor_reference": receipt["reference"],
                       "processor_reference_spoken": spoken_reference(receipt["reference"]),
                       "amount_spoken": spoken_amount(record["balance_cents"])})
    else:
        result.update({"payment_status": "pending",
                       "next_step": ("The processor's receipt could not be verified, so the payment is not "
                                     "confirmed. Do not say it is paid. The payments team checks it; the order "
                                     "stays on hold until then.")})
    return result


def leave_payment_pending(service: PaymentService, customer_id: Optional[str], order_number: Any) -> dict:
    if _carries_card_data(order_number):
        return _card_data_refusal()
    order, record = service.order(customer_id, order_number)
    if record is None:
        return _not_found(order)
    service.pending_left[order] = {"balance_cents": record["balance_cents"]}
    return {"status": "pending", "reason": "caller_declined_secure_step", "order": order, "effects": 0,
            "payment_status": "unpaid", "approved_alternative": APPROVED_ALTERNATIVE,
            "next_step": "Nothing was charged. Do not take card details on the call."}


# ----------------------------------------------------------------------------
# Receipts the tools send to the caller themselves
# ----------------------------------------------------------------------------


def customer_receipt(tool_name: str, result: dict) -> Optional[str]:
    """The receipt a tool speaks to the caller itself, or None. Never holds card data."""
    status = result.get("status")
    order = result.get("order")
    if tool_name == "send_secure_payment_link" and status == "link_sent":
        text = (f"I've sent a secure payment link {result['sent_to']} for order {spoken_order(order)}. "
                f"Your payment is pending until our payment processor confirms it.")
    elif tool_name == "check_payment_status" and status == "succeeded":
        text = (f"Payment received for order {spoken_order(order)}: {result['amount_spoken']}. "
                f"Your processor reference is {result['processor_reference_spoken']}.")
    elif tool_name == "check_payment_status" and status == "pending" and result.get("reason") == \
            "unverified_processor_receipt":
        text = (f"Order {spoken_order(order)} is not confirmed as paid yet: I can't verify the processor's "
                f"receipt, so the payments team will check it.")
    elif tool_name == "leave_payment_pending" and status == "pending":
        text = (f"Order {spoken_order(order)} stays unpaid and nothing was charged. You can "
                f"{APPROVED_ALTERNATIVE}.")
    else:
        return None
    if pci.contains_payment_secret(text):
        return None
    return text
