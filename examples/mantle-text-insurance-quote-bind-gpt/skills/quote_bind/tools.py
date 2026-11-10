"""Quote-and-bind tools. The guard runs in lib.quotes, not in the prompt.

The customer id comes from project memory, written once at session start.
What the engine reads back for each confirmation (the answers, the offer)
lives in skill memory that only these tools write (never ``llm_settable``), so
the answers the customer confirms and the offer they agree to bind are always
the ones the tools resolved. The model passes a quote id, an offer id copied
from a tool result, a question id and the customer's answer. No tool takes a
price, a fact or a policy number.
"""

from __future__ import annotations

from typing import Optional

from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult

from lib import quotes as hq

CUSTOMER_KEY = "project.customer_id"


def _conversation_id() -> str:
    try:
        from rasa.mantle.orchestration.turn_context import current_turn_context

        return current_turn_context().sender_id
    except Exception:
        return "offline"


def _service() -> hq.QuoteService:
    return hq.service_for(_conversation_id())


def _get(context: Optional[ToolContext], key: str) -> Optional[str]:
    return (context.memory.get(key) if context is not None else None) or None


def _customer(context: Optional[ToolContext]) -> Optional[str]:
    return _get(context, CUSTOMER_KEY)


def _remember(context: Optional[ToolContext], svc: hq.QuoteService, customer_id: Optional[str], quote_id: str) -> None:
    """Write what the next confirmation will read back, from the service's own state."""
    quote = svc.quote_of(customer_id, quote_id)
    if context is None or quote is None:
        return
    offer = svc.current_offer(quote)
    context.memory.set("quote_id", hq.normalise_id(quote_id))
    context.memory.set("answers_summary", hq.answers_summary(svc, quote))
    context.memory.set("answers_hash", hq.answers_hash(quote["answers"]))
    live = offer is not None and offer["status"] == "offered"
    context.memory.set("offer_id", offer["offer_id"] if live else "")
    context.memory.set("offer_summary", hq.offer_summary(svc, quote, offer) if live else "")


@tool(
    description=(
        "Read one of the customer's saved quotes: its state (estimate, offer, "
        "referred, bind_pending or bound), the indicative estimate from the quote "
        "screen, the material answers on file and the current underwritten offer. "
        "Without a quote_id it lists the customer's quotes. Never binds anything."
    )
)
async def get_quote(quote_id: str = "", context: ToolContext = None) -> ToolResult:
    """Read a quote.

    Args:
        quote_id: The quote id, for example HC-Q-RN-6120. Empty to list the customer's quotes.
    """
    svc = _service()
    result = hq.get_quote(svc, _customer(context), quote_id or None)
    if quote_id and result.get("status") == "found":
        _remember(context, svc, _customer(context), quote_id)
    return ToolResult(llm_response=result)


@tool(
    description=(
        "Send a quote's current material answers to HarborCover underwriting and "
        "get a firm, versioned offer (or a referral to an underwriter). An offer is "
        "not active cover and binds nothing."
    )
)
async def request_underwritten_offer(quote_id: str, context: ToolContext = None) -> ToolResult:
    """Request an underwritten offer.

    Args:
        quote_id: The quote id, for example HC-Q-RN-6120.
    """
    svc = _service()
    result = hq.request_underwritten_offer(svc, _customer(context), quote_id)
    _remember(context, svc, _customer(context), quote_id)
    return ToolResult(llm_response=result)


@tool(
    description=(
        "Change one material answer on a quote when the customer corrects it. Any "
        "change withdraws the current offer; a new one must be requested before "
        "binding. Questions: address, contents_value_usd, prior_claims_3y, "
        "dog_on_premises, smoke_alarms, start_date (renters); vehicle, annual_miles, "
        "prior_claims_3y, named_drivers, garaging_address, start_date (auto); "
        "address, contents_value_usd, prior_claims_3y, start_date (condo)."
    )
)
async def update_quote_answer(quote_id: str, question: str, value: str, context: ToolContext = None) -> ToolResult:
    """Change one answer.

    Args:
        quote_id: The quote id, for example HC-Q-RN-6120.
        question: The question id, for example dog_on_premises.
        value: The customer's new answer: digits for numbers, yes or no, dates as YYYY-MM-DD.
    """
    svc = _service()
    result = hq.update_quote_answer(svc, _customer(context), quote_id, question, value)
    _remember(context, svc, _customer(context), quote_id)
    return ToolResult(llm_response=result)


@tool(
    description=(
        "Record that the customer confirmed the material answers on a quote. The "
        "engine reads the answers back and asks the customer first. Call it when "
        "the customer agrees to review the answers."
    )
)
async def confirm_material_answers(quote_id: str, context: ToolContext = None) -> ToolResult:
    """Confirm the answers the engine read back.

    Args:
        quote_id: The quote id, for example HC-Q-RN-6120.
    """
    result = hq.confirm_material_answers(
        _service(), _customer(context), quote_id, _get(context, "quote_id"), _get(context, "answers_hash")
    )
    return ToolResult(llm_response=result)


@tool(
    description=(
        "Ask the HarborCover binding service to bind the current underwritten "
        "offer, identified by its offer_id. The engine reads the offer back and "
        "asks the customer first. Returns a policy number only when the binding "
        "service confirms with a matching receipt; otherwise the offer stays unbound."
    )
)
async def bind_offer(offer_id: str, context: ToolContext = None) -> ToolResult:
    """Bind one offer.

    Args:
        offer_id: The offer_id from request_underwritten_offer, for example HC-OFR-6120-1.
    """
    result = hq.bind_offer(
        _service(), _customer(context), offer_id, _get(context, "offer_id"), request_key=_conversation_id()
    )
    return ToolResult(llm_response=result)


@tool(
    description=(
        "Look up a bind request by its offer_id after bind_offer came back pending. "
        "Never sends a new bind."
    )
)
async def check_bind_status(offer_id: str, context: ToolContext = None) -> ToolResult:
    """Look up a bind request.

    Args:
        offer_id: The offer_id that was sent to bind, for example HC-OFR-6121-1.
    """
    return ToolResult(
        llm_response=hq.check_bind_status(_service(), _customer(context), offer_id, request_key=_conversation_id())
    )


@tool(
    description=(
        "Ask the HarborCover underwriting desk to call the customer back about a "
        "quote: a referral, a bind with no receipt, or a change to a bound policy. "
        "Returns a reference. Binds nothing."
    )
)
async def request_underwriting_callback(quote_id: str, reason: str, context: ToolContext = None) -> ToolResult:
    """Request an underwriting callback.

    Args:
        quote_id: The quote id, for example HC-Q-AU-6121.
        reason: One short sentence, for example bind not confirmed by the binding service.
    """
    return ToolResult(
        llm_response=hq.underwriting_callback(_service(), _customer(context), quote_id, reason)
    )
