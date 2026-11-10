"""The model supplies words; the current Rasa sender owns the fixture binding."""
import asyncio
import json
from urllib.error import URLError
from urllib.request import Request, urlopen
from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult
from rasa.shared.core.events import UserUttered

DEMO_CODES = {"111111": "demo-a", "222222": "demo-b"}
BINDINGS = {}
PROPOSALS = {}


def sender():
    from rasa.mantle.orchestration.turn_context import current_turn_context
    return current_turn_context().sender_id


@tool(description="Select public fictional fixture 111111 or 222222 supplied by the user. This does not authenticate anyone.")
async def select_demo(code: str, context: ToolContext = None) -> ToolResult:
    owner = DEMO_CODES.get(code)
    if owner is None:
        return ToolResult(llm_response={"status": "unknown_demo"})
    key = sender()
    if key in BINDINGS and BINDINGS[key] != owner:
        return ToolResult(llm_response={"status": "demo_identity_changed"})
    BINDINGS[key] = owner
    return ToolResult(llm_response={"status": "demo_ready"})


def request_worker(path, body):
    request = Request("http://127.0.0.1:5029" + path, method="POST",
                      data=json.dumps(body).encode(),
                      headers={"Content-Type": "application/json"})
    try:
        with urlopen(request, timeout=3) as response:
            result = json.load(response)
        if not isinstance(result, dict) or not isinstance(result.get("status"), str):
            raise ValueError()
        return result
    except (URLError, OSError, ValueError):
        return {"status": "worker_unavailable"}


def last_user(context):
    if context is None:
        return None
    return next((event for event in reversed(context.events) if isinstance(event, UserUttered)), None)


@tool(description="Propose a fictional account for the current user's transaction request, then ask them to confirm it. Reads no transactions.")
async def propose_recent_transactions(context: ToolContext = None) -> ToolResult:
    key = sender()
    owner = BINDINGS.get(key)
    if owner is None:
        return ToolResult(llm_response={"status": "needs_demo_code"})
    user = last_user(context)
    if user is None:
        return ToolResult(llm_response={"status": "context_required"})
    PROPOSALS.pop(key, None)
    result = await asyncio.to_thread(request_worker, "/propose",
                                    {"owner": owner, "conversation": key, "message": user.text})
    token = result.pop("proposal_token", None)
    if result.get("status") == "account_proposal" and token:
        if context.is_cancelled:
            return ToolResult(llm_response={"status": "interrupted"})
        await context.send(f"I can read your {result['label']}. Shall I use that account?")
        if context.is_cancelled:
            return ToolResult(llm_response={"status": "interrupted"})
        PROPOSALS[key] = (token, owner, user.timestamp)
        result["status"] = "confirmation_requested"
    return ToolResult(llm_response=result)


@tool(description="Read the proposed fictional account only after a new user message explicitly says yes; no model-provided account, owner or confirmation arguments.")
async def read_confirmed_transactions(context: ToolContext = None) -> ToolResult:
    key = sender()
    proposal = PROPOSALS.get(key)
    user = last_user(context)
    if proposal is None:
        return ToolResult(llm_response={"status": "needs_account_proposal"})
    token, owner, created = proposal
    if user is None or user.timestamp <= created:
        return ToolResult(llm_response={"status": "needs_confirmation"})
    later_users = [event for event in context.events
                   if isinstance(event, UserUttered) and event.timestamp > created]
    if len(later_users) != 1:
        del PROPOSALS[key]
        await asyncio.to_thread(request_worker, "/cancel",
                                {"owner": owner, "conversation": key, "token": token})
        return ToolResult(llm_response={"status": "proposal_expired"})
    text = (user.text or "").strip().lower().strip(".!?")
    if text in {"no", "no thanks", "cancel"}:
        path = "/cancel"
    elif text in {"yes", "yes please", "confirm"}:
        path = "/confirm"
    else:
        return ToolResult(llm_response={"status": "needs_confirmation"})
    del PROPOSALS[key]
    result = await asyncio.to_thread(request_worker, path,
                                    {"owner": owner, "conversation": key, "token": token})
    return ToolResult(llm_response=result)
