"""Transfer tools. The step-up guard runs in lib.northgate, not in the prompt.

The model passes an account, a destination, an amount, a reference copied
from a tool result and the code the customer typed. It never passes a risk
level, a verification level, a customer id or a contract fact.
"""

from __future__ import annotations

from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult

from lib import northgate as ng


# Same helpers as tools/northgate_shared.py, repeated because skill tool
# modules import only from lib/.
def _conversation_id() -> str:
    try:
        from rasa.mantle.orchestration.turn_context import current_turn_context

        return current_turn_context().sender_id
    except Exception:
        return "offline"


def service() -> ng.PaymentsService:
    return ng.service_for(_conversation_id())


def session_customer_id(context: ToolContext | None) -> str:
    """The customer bound to this session, from trusted project memory."""
    if context is None:
        return ng.DEMO_CUSTOMER_ID
    return context.memory.get("project.customer_id") or ng.DEMO_CUSTOMER_ID


@tool(
    description=(
        "Assess the risk of one transfer and return the verification level it "
        "needs. Call it for exactly the account, destination and amount the "
        "customer wants now, and again whenever any of them changes."
    )
)
async def assess_transfer(from_account: str, destination: str, amount: str, context: ToolContext = None) -> ToolResult:
    """Assess a transfer.

    Args:
        from_account: The account to pay from, for example "current" or NB-ACC-3101.
        destination: A saved payee (nickname or id, for example "Mum" or NB-PAY-01) or the customer's other account.
        amount: The amount in pounds, for example "150" or "1,500.00".
    """
    return ToolResult(llm_response=ng.assess_transfer(
        service(), session_customer_id(context), from_account, destination, amount))


@tool(
    description=(
        "Send a one-time code to the customer's registered phone for one "
        "assessed transfer that needs level 2. The code verifies that transfer only."
    )
)
async def start_step_up(assessment_ref: str, context: ToolContext = None) -> ToolResult:
    """Start a step-up.

    Args:
        assessment_ref: The assessment_ref from assess_transfer, for example NB-RA-1A2B3C4D.
    """
    return ToolResult(llm_response=ng.start_step_up(service(), session_customer_id(context), assessment_ref))


@tool(
    description=(
        "Check the one-time code the customer typed, for the assessment the "
        "code was sent for."
    )
)
async def submit_step_up_code(assessment_ref: str, code: str, context: ToolContext = None) -> ToolResult:
    """Check a step-up code.

    Args:
        assessment_ref: The assessment the code was sent for.
        code: The code exactly as the customer typed it.
    """
    return ToolResult(llm_response=ng.submit_step_up_code(
        service(), session_customer_id(context), assessment_ref, code))


@tool(
    description=(
        "Send one assessed transfer. Pass the assessment_ref and the same "
        "account, destination and amount it was assessed for. The bank checks "
        "the assessment and verification and returns succeeded or blocked."
    )
)
async def submit_transfer(
    assessment_ref: str, from_account: str, destination: str, amount: str, context: ToolContext = None
) -> ToolResult:
    """Send a transfer.

    Args:
        assessment_ref: The assessment_ref of the transfer, from assess_transfer.
        from_account: The account to pay from.
        destination: The payee or account to pay.
        amount: The amount in pounds.
    """
    return ToolResult(llm_response=ng.submit_transfer(
        service(), session_customer_id(context), assessment_ref, from_account, destination, amount))


@tool(
    description=(
        "Suspend a transfer whose risk cannot be resolved in chat (level 3, a "
        "locked code, or the customer wants the team) and route it to the "
        "identity risk team. Nothing is sent. Returns a reference."
    )
)
async def suspend_transfer_and_route(assessment_ref: str, reason: str, context: ToolContext = None) -> ToolResult:
    """Suspend and route.

    Args:
        assessment_ref: The transfer's assessment_ref.
        reason: One short sentence, for example "level 3 needed" or "customer asked for the team".
    """
    return ToolResult(llm_response=ng.suspend_transfer_and_route(
        service(), session_customer_id(context), assessment_ref, reason))
