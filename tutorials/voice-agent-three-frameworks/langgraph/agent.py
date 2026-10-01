# concern: agent-logic
"""The Cedar Clinic refill agent: LangChain's create_agent over the shared cedar_clinic API.

Every rule about records, matching and receipts runs in cedar_clinic, the
same code the Rasa and Strands versions call. This file binds it to
LangGraph: the model (GPT-5.5 at reasoning_effort low, through
langchain-openai), the system prompt built from cedar_clinic.instructions,
the five tools with the names, descriptions and parameters in
cedar_clinic.tools.TOOL_SPECS, and a checkpointer keyed by the conversation
id. The regions marked refill-guard are the state only tools write; the rest
of the guard is RefillGuard in guard.py.
"""

from __future__ import annotations

import json
import os
from typing import Any

from cedar_clinic import instructions
from cedar_clinic import tools as clinic
from cedar_clinic.tools import TOOL_SPECS
from langchain.agents import create_agent
from langchain.tools import ToolRuntime, tool
from langchain_core.messages import ToolMessage
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command
from pydantic import Field, create_model

# concern-begin: refill-guard
from guard import RefillGuard, llm_classifier
# concern-end

#: The model, the same for all three versions. The runner points the openai
#: client at its meter through OPENAI_BASE_URL.
MODEL = os.environ.get("CEDAR_MODEL", "gpt-5.5-2026-04-23")
REASONING_EFFORT = "low"

#: The shared procedure is already written for a framework that reads the
#: medicine back as part of sending, so it is used verbatim.
SYSTEM_PROMPT = instructions.system_prompt()


def make_model(**kwargs: Any) -> ChatOpenAI:
    """GPT-5.5 through Chat Completions, streamed so replies can be spoken sentence by sentence."""
    return ChatOpenAI(model=MODEL, reasoning_effort=REASONING_EFFORT, use_responses_api=True, **kwargs)


def _args_schema(name: str):
    """The tool's parameters exactly as TOOL_SPECS states them."""
    spec = TOOL_SPECS[name]
    fields = {
        param: (str, Field(... if param in spec["required"] else "", description=info["description"]))
        for param, info in spec["parameters"].items()
    }
    return create_model(name, **fields)


def _conversation_id(runtime: ToolRuntime) -> str:
    """The thread id, which the voice loop sets to the X-Rasa-Sender-Id conversation id."""
    return runtime.config["configurable"]["thread_id"]


def _reply(runtime: ToolRuntime, result: dict, **update: Any) -> Command:
    return Command(update={**update, "messages": [
        ToolMessage(json.dumps(result), tool_call_id=runtime.tool_call_id)]})


def _spec(name: str) -> dict:
    return {"description": TOOL_SPECS[name]["description"], "args_schema": _args_schema(name)}


@tool("verify_patient", **_spec("verify_patient"))
async def verify_patient(full_name: str, date_of_birth: str, runtime: ToolRuntime) -> Command:
    result = clinic.verify_patient(_conversation_id(runtime), full_name, date_of_birth)
    update: dict = {}
    # concern-begin: refill-guard
    # The patient id goes to state, never to the model. The first verified
    # patient stays: a call verified as one patient cannot become another.
    if result["status"] == "verified":
        current = runtime.state.get("patient_id")
        if not current:
            update = {"patient_id": result["patient_id"], "patient_first_name": result["first_name"]}
        elif current != result["patient_id"]:
            result = {"status": "not_verified", "reason": "already_verified_as_another_patient",
                      "next_step": "This call is verified for a different patient. Do not act for this one."}
    # concern-end
    return _reply(runtime, clinic.for_model(result), **update)


@tool("select_medication", **_spec("select_medication"))
async def select_medication(medication_name: str, runtime: ToolRuntime) -> Command:
    result = clinic.select_medication(_conversation_id(runtime), runtime.state.get("patient_id"), medication_name)
    # concern-begin: refill-guard
    # A new selection always replaces the old one, so a correction can never
    # leave the previous medicine selected for the confirmation step.
    update = {"selected_record_id": result.get("record_id", ""),
              "selected_label": result.get("medication_label", "")}
    # concern-end
    return _reply(runtime, result, **update)


@tool("send_refill_request", **_spec("send_refill_request"))
async def send_refill_request(record_id: str, runtime: ToolRuntime, patient_note: str = "") -> Command:
    result = clinic.send_refill_request(_conversation_id(runtime), runtime.state.get("patient_id"),
                                        runtime.state.get("selected_record_id"), record_id, patient_note)
    return _reply(runtime, result)


@tool("check_request_status", **_spec("check_request_status"))
async def check_request_status(submission_key: str, runtime: ToolRuntime) -> Command:
    return _reply(runtime, clinic.check_request_status(
        _conversation_id(runtime), runtime.state.get("patient_id"), submission_key))


@tool("route_clinical_question", **_spec("route_clinical_question"))
async def route_clinical_question(question: str, runtime: ToolRuntime, record_id: str = "") -> Command:
    return _reply(runtime, clinic.route_clinical_question(
        _conversation_id(runtime), runtime.state.get("patient_id"), question, record_id or None))


TOOLS = [verify_patient, select_medication, send_refill_request, check_request_status, route_clinical_question]


def build_agent(model: Any = None, *, classify: Any = None, checkpointer: Any = None):
    """The compiled graph. One checkpointer per process; thread_id is the conversation id."""
    model = model if model is not None else make_model(streaming=True)
    return create_agent(
        model=model,
        tools=TOOLS,
        system_prompt=SYSTEM_PROMPT,
        # concern-begin: refill-guard
        middleware=[RefillGuard(classify or llm_classifier(make_model()))],
        # concern-end
        checkpointer=checkpointer or InMemorySaver(),
    )
