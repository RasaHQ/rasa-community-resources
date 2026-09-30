# concern: refill-guard
"""The refill guard: agent middleware, private state and interrupt().

The hard guarantee is: no refill request without a patient verified on this
call and a medicine the caller confirmed on a later turn than its selection.
cedar_clinic refuses a send it can see is wrong. What this module adds is
what the library cannot see, with LangChain and LangGraph's own mechanisms:

- ``RefillState``: the verified patient id and the selected record entry are
  graph state marked ``PrivateStateAttr``, so they are not in the graph's
  input or output schema. Only the tools write them, through the ``Command``
  updates they return (agent.py); no tool takes a patient id from the model.
- ``RefillGuard.awrap_model_call``: ``send_refill_request`` is left out of the
  tools offered to the model until ``select_medication`` has put a record id
  in state.
- ``RefillGuard.awrap_tool_call``: a ``send_refill_request`` call is refused
  (fails closed) unless its record id is the one selected. Otherwise the
  guard calls ``interrupt()`` with the contract's question and the selected
  medicine read back. The run ends there and the voice loop speaks the
  question. The call resumes only with ``Command(resume=...)``, which the voice
  loop sends with the caller's next final transcript, so the answer is always
  from a later caller turn. The answer is classified by the model (as Rasa's
  engine also leaves to the model), recorded with the clinic with the
  caller's words, and only a yes runs the tool.
"""

from __future__ import annotations

import json
from typing import Annotated, Any, Awaitable, Callable

from cedar_clinic import tools as clinic
from langchain.agents.middleware import AgentMiddleware, AgentState, ModelRequest, ToolCallRequest
from langchain.agents.middleware.types import PrivateStateAttr
from langchain_core.messages import ToolMessage
from langgraph.types import interrupt
from pydantic import BaseModel, Field
from typing_extensions import NotRequired

SEND = "send_refill_request"
MECHANISM = "langgraph interrupt() in RefillGuard.awrap_tool_call"

Classifier = Callable[[str, str], Awaitable[bool]]


class RefillState(AgentState):
    """Agent state plus what only tools write. Private: not settable from the graph's input."""

    patient_id: NotRequired[Annotated[str, PrivateStateAttr]]
    patient_first_name: NotRequired[Annotated[str, PrivateStateAttr]]
    selected_record_id: NotRequired[Annotated[str, PrivateStateAttr]]
    selected_label: NotRequired[Annotated[str, PrivateStateAttr]]


class CallerAnswer(BaseModel):
    confirmed: bool = Field(description="True only when the caller said yes to sending this request for this medicine.")


CLASSIFY_PROMPT = (
    "A caller on a clinic's prescription line was asked: \"{question}\"\n"
    "The caller answered: \"{answer}\"\n"
    "Did the caller say yes to sending this request for this medicine? A no, a different medicine, "
    "a question without a yes, or anything unclear is not a yes."
)


def llm_classifier(model: Any) -> Classifier:
    """Yes or no from the model, with structured output: the judgement Rasa's engine also leaves to the model."""
    structured = model.with_structured_output(CallerAnswer, method="json_schema")

    async def classify(question: str, answer: str) -> bool:
        result = await structured.ainvoke(CLASSIFY_PROMPT.format(question=question, answer=answer))
        return bool(result.confirmed)

    return classify


def _blocked(call: dict, reason: str, next_step: str) -> ToolMessage:
    return ToolMessage(json.dumps({"status": "blocked", "reason": reason, "effects": 0, "next_step": next_step}),
                       tool_call_id=call["id"], name=SEND)


class RefillGuard(AgentMiddleware[RefillState]):
    state_schema = RefillState

    def __init__(self, classify: Classifier) -> None:
        super().__init__()
        self.classify = classify

    async def awrap_model_call(self, request: ModelRequest, handler: Callable) -> Any:
        """Hide send_refill_request until a record entry is selected."""
        if not request.state.get("selected_record_id"):
            request = request.override(tools=[t for t in request.tools if getattr(t, "name", None) != SEND])
        return await handler(request)

    async def awrap_tool_call(self, request: ToolCallRequest, handler: Callable) -> Any:
        call = request.tool_call
        if call["name"] != SEND:
            return await handler(request)
        state = request.state
        selected = state.get("selected_record_id") or ""
        record_id = str(call["args"].get("record_id") or "").strip().upper()
        if not selected or record_id != selected:
            return _blocked(call, "medication_not_resolved",
                            "Call select_medication first and send only the record_id it returned.")
        question = clinic.confirmation_question(state.get("selected_label") or "")
        # Everything above runs again on resume and has no side effects.
        resumed = interrupt({"kind": "confirm_refill", "question": question, "record_id": record_id})
        answer = str(resumed.get("text") if isinstance(resumed, dict) else resumed or "").strip()
        confirmed = bool(answer) and await self.classify(question, answer)
        conversation_id = request.runtime.config["configurable"]["thread_id"]
        clinic.record_confirmation(conversation_id, record_id, confirmed, mechanism=MECHANISM,
                                   question=question, answer=answer)
        if not confirmed:
            request.runtime.stream_writer({"say": clinic.DECLINED_TEXT})
            return ToolMessage(json.dumps({
                "status": "declined", "effects": 0, "caller_answer": answer,
                "caller_was_told": clinic.DECLINED_TEXT,
                "next_step": ("Nothing was sent and the caller has been told so; do not repeat it. If the caller "
                              "named a different medicine, call select_medication with it. Otherwise answer "
                              "what they said or ask what else they need."),
            }), tool_call_id=call["id"], name=SEND)
        # A progress event for the voice loop, which may say a filler while the request is sent.
        request.runtime.stream_writer({"confirmed": record_id})
        result = await handler(request)
        return _with_answer(result, answer)


def _with_answer(result: Any, answer: str) -> Any:
    """The tool's result with the caller's words added, so the model sees what else they said."""
    messages = result.update.get("messages") if hasattr(result, "update") and isinstance(result.update, dict) \
        else [result]
    for message in messages or []:
        if isinstance(message, ToolMessage) and isinstance(message.content, str):
            try:
                body = json.loads(message.content)
            except ValueError:
                continue
            message.content = json.dumps({"caller_answer": answer, **body})
    return result
