# concern: agent-logic
"""The Cedar Clinic agent on Strands: the model, the prompt, the five tools and one turn.

Every rule about records, matching and receipts runs in ``cedar_clinic``,
the same code the Rasa and LangGraph versions call. This file binds it to
Strands:

- ``OpenAIResponsesModel`` (the Responses API, streamed, ``store`` off) with
  GPT-5.5 at reasoning effort low. Chat Completions refuses function tools
  with ``reasoning_effort`` on this model (HTTP 400, checked 2026-10-01), so
  ``OpenAIModel`` cannot be used. The openai SDK reads ``OPENAI_BASE_URL``,
  so the spec runner's meter sees every call.
- The five tools as ``@tool`` functions whose names, descriptions and
  parameter schemas are ``cedar_clinic.tools.TOOL_SPECS`` verbatim.
- One ``Agent`` per conversation id, kept in ``CONVERSATIONS``. The
  conversation id reaches the tools through ``invocation_state``.
- ``Conversation.turn(text)``: one caller turn as a stream of things to say.

The regions marked refill-guard are the state only tools write (the verified
patient, the selected entry) and the interrupt/resume half of the guard; the
decision half is ``guard.py``.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, AsyncIterator, Optional

from cedar_clinic import instructions
from cedar_clinic import tools as clinic
from cedar_clinic.tools import TOOL_SPECS
from strands import Agent, tool
from strands.models.openai_responses import OpenAIResponsesModel
from strands.tools.executors import SequentialToolExecutor
from strands.types.tools import ToolContext

from guard import RefillGuard

# The same snapshot and effort as the other two versions. Reasoning models
# reject any temperature but the default (HTTP 400, checked 2026-10-01), so
# none is set. On the Responses API the effort is the `reasoning` object.
MODEL_ID = os.environ.get("CEDAR_MODEL", "gpt-5.5-2026-04-23")
MODEL_PARAMS = {"reasoning": {"effort": "low"}}

SYSTEM_PROMPT = instructions.system_prompt()


def _schema(name: str) -> dict:
    return {"json": clinic.json_schema(name)["parameters"]}


def _conversation_id(ctx: ToolContext) -> str:
    return str(ctx.invocation_state.get("conversation_id") or "offline")


def _state(ctx: ToolContext, key: str) -> Optional[str]:
    return ctx.agent.state.get(key) or None


@tool(name="verify_patient", description=TOOL_SPECS["verify_patient"]["description"],
      inputSchema=_schema("verify_patient"), context=True)
def verify_patient(full_name: str, date_of_birth: str, tool_context: ToolContext) -> dict:
    result = clinic.verify_patient(_conversation_id(tool_context), full_name, date_of_birth)
    # concern-begin: refill-guard
    # The patient id goes to agent.state, which no model tool can write, and
    # only this tool writes it. Write-once: a call verified as one patient
    # cannot become another.
    if result["status"] == "verified":
        known = _state(tool_context, "patient_id")
        if not known:
            tool_context.agent.state.set("patient_id", result["patient_id"])
        elif known != result["patient_id"]:
            return {"status": "not_verified", "reason": "already_verified_as_another_patient",
                    "next_step": "This call is verified for a different patient. Do not act for this one."}
    # concern-end
    return clinic.for_model(result)


@tool(name="select_medication", description=TOOL_SPECS["select_medication"]["description"],
      inputSchema=_schema("select_medication"), context=True)
def select_medication(medication_name: str, tool_context: ToolContext) -> dict:
    result = clinic.select_medication(_conversation_id(tool_context), _state(tool_context, "patient_id"),
                                      medication_name)
    # concern-begin: refill-guard
    # A new selection always replaces the old one, so the guard reads back and
    # gates on the entry selected last.
    tool_context.agent.state.set("selected_record_id", result.get("record_id", ""))
    tool_context.agent.state.set("selected_medication_label", result.get("medication_label", ""))
    # concern-end
    return result


@tool(name="send_refill_request", description=TOOL_SPECS["send_refill_request"]["description"],
      inputSchema=_schema("send_refill_request"), context=True)
def send_refill_request(record_id: str, tool_context: ToolContext, patient_note: str = "") -> dict:
    # Runs only after guard.py's Confirm intervention was answered yes on a
    # later caller turn; the confirmation is recorded there.
    return clinic.send_refill_request(_conversation_id(tool_context), _state(tool_context, "patient_id"),
                                      _state(tool_context, "selected_record_id"), record_id, patient_note)


@tool(name="check_request_status", description=TOOL_SPECS["check_request_status"]["description"],
      inputSchema=_schema("check_request_status"), context=True)
def check_request_status(submission_key: str, tool_context: ToolContext) -> dict:
    return clinic.check_request_status(_conversation_id(tool_context), _state(tool_context, "patient_id"),
                                       submission_key)


@tool(name="route_clinical_question", description=TOOL_SPECS["route_clinical_question"]["description"],
      inputSchema=_schema("route_clinical_question"), context=True)
def route_clinical_question(question: str, tool_context: ToolContext, record_id: str = "") -> dict:
    return clinic.route_clinical_question(_conversation_id(tool_context), _state(tool_context, "patient_id"),
                                          question, record_id or None)


TOOLS = [verify_patient, select_medication, send_refill_request, check_request_status, route_clinical_question]


def build_model() -> OpenAIResponsesModel:
    return OpenAIResponsesModel(client_args={"api_key": os.environ.get("OPENAI_API_KEY", "")}, model_id=MODEL_ID,
                                params=dict(MODEL_PARAMS))


@dataclass
class Say:
    """Something for the voice loop to speak or act on.

    kind: ``delta`` (streamed model text), ``end`` (a model message is
    complete; ``text`` is all of it), ``fixed`` (a whole message, ``source``
    says whose words), ``tools`` (tools finished; ``text`` names them,
    ``source`` is ``ok`` or ``cancelled``).
    """

    kind: str
    text: str = ""
    source: str = "model"


class Conversation:
    """One caller's conversation: a Strands Agent and its pending confirmation."""

    def __init__(self, conversation_id: str, model: Any = None) -> None:
        self.conversation_id = conversation_id
        self.guard = RefillGuard(conversation_id)
        self.agent = Agent(
            model=model if model is not None else build_model(),
            tools=list(TOOLS),
            system_prompt=SYSTEM_PROMPT,
            # The greeting the voice loop speaks on connect, so the model sees it.
            messages=[{"role": "assistant", "content": [{"text": instructions.GREETING}]}],
            # One tool at a time, in the model's order: select_medication reads
            # the patient id verify_patient writes in the same batch.
            tool_executor=SequentialToolExecutor(),
            interventions=[self.guard],
            callback_handler=None,
            agent_id=_agent_id(conversation_id),
        )
        # concern-begin: refill-guard
        self.pending: list = []
        # concern-end

    async def turn(self, text: str) -> AsyncIterator[Say]:
        """One caller turn: stream what to say, in order."""
        prompt: Any = text
        # concern-begin: refill-guard
        # A pending Confirm interrupt is answered with the caller's words from
        # this turn, the only way it is ever resumed; guard.py decides.
        if self.pending:
            prompt = [{"interruptResponse": {"interruptId": i.id, "response": {"answer": text}}}
                      for i in self.pending]
            self.pending = []
        # concern-end
        tool_names: dict[str, str] = {}
        buffered: list[str] = []
        result = None
        async for event in self.agent.stream_async(prompt, invocation_state={"conversation_id": self.conversation_id}):
            if "data" in event and isinstance(event["data"], str) and event["data"]:
                buffered.append(event["data"])
                yield Say("delta", event["data"])
            elif "message" in event:
                message = event["message"]
                content = message.get("content") or []
                if message.get("role") == "assistant":
                    for block in content:
                        if "toolUse" in block:
                            tool_names[block["toolUse"]["toolUseId"]] = block["toolUse"]["name"]
                    if buffered:
                        yield Say("end", "".join(buffered))
                        buffered = []
                else:
                    results = [b["toolResult"] for b in content if "toolResult" in b]
                    for r in results:
                        name = tool_names.get(r.get("toolUseId")) or self._tool_name(r.get("toolUseId"))
                        cancelled = r.get("status") == "error"
                        # concern-begin: refill-guard
                        if name == "send_refill_request" and self.guard.declined_on(r):
                            yield Say("fixed", clinic.DECLINED_TEXT, "declined")
                        # concern-end
                        yield Say("tools", name, "cancelled" if cancelled else "ok")
            elif "result" in event:
                result = event["result"]
        if buffered:
            yield Say("end", "".join(buffered))
        # concern-begin: refill-guard
        if result is not None and result.stop_reason == "interrupt":
            self.pending = list(result.interrupts)
            for interrupt in self.pending:
                # The Confirm prompt: cedar_clinic's read-back question, verbatim.
                yield Say("fixed", str(interrupt.reason), "confirmation")
        # concern-end

    def _tool_name(self, tool_use_id: Any) -> str:
        """The tool a result belongs to, from the history (a resumed call's toolUse is from an earlier turn)."""
        for message in reversed(self.agent.messages):
            for block in message.get("content") or []:
                if "toolUse" in block and block["toolUse"].get("toolUseId") == tool_use_id:
                    return block["toolUse"]["name"]
        return ""


def _agent_id(conversation_id: str) -> str:
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in conversation_id)[:100] or "call"


CONVERSATIONS: dict[str, Conversation] = {}


def conversation(conversation_id: str) -> Conversation:
    """The conversation for this id, created on first use."""
    if conversation_id not in CONVERSATIONS:
        CONVERSATIONS[conversation_id] = Conversation(conversation_id)
    return CONVERSATIONS[conversation_id]


def tool_specs() -> dict[str, dict]:
    """What the model is offered, by name: for the parity test."""
    return {t.tool_name: json.loads(json.dumps(t.tool_spec)) for t in TOOLS}
