# concern: agent-logic
"""Agno owns the agent loop and native HITL pause; voice is application code."""
from __future__ import annotations
import os
from dataclasses import dataclass
from typing import AsyncIterator

from agno.agent import Agent
from agno.db.in_memory import InMemoryDb
from agno.models.openai.responses import OpenAIResponses
from agno.models.message import Message
from agno.run.agent import RunContentEvent, RunPausedEvent, RunCompletedEvent, ToolCallCompletedEvent
from agno.tools.function import Function
from cedar_clinic import instructions
from cedar_clinic import tools as clinic
from guard import caller_said_yes

SYSTEM_PROMPT = instructions.system_prompt()
MODEL_ID = os.environ.get('CEDAR_MODEL', 'gpt-5.5-2026-04-23')


@dataclass
class Say:
    kind: str
    text: str = ''
    source: str = 'model'


class Conversation:
    def __init__(self, cid, model=None):
        self.cid = cid
        # concern-begin: refill-guard
        self.patient_id = None
        self.selected_id = ''
        self.selected_label = ''
        self.pending = None
        self.caller_answer = ''
        # concern-end
        self.tools = self._tools()
        self.agent = Agent(model=model if model is not None else OpenAIResponses(
            id=MODEL_ID, reasoning={'effort': 'low'}, store=False,
            use_previous_response_id=False, parallel_tool_calls=False,
            base_url=os.environ.get('OPENAI_BASE_URL')),
            instructions=SYSTEM_PROMPT, tools=self.tools,
            db=InMemoryDb(), cache_session=True, add_history_to_context=True,
            add_session_state_to_context=False, enable_agentic_memory=False,
            telemetry=False, markdown=False, tool_call_limit=30)
        self.first_turn = True

    def _tools(self):
        def verify_patient(full_name: str, date_of_birth: str):
            result = clinic.verify_patient(self.cid, full_name, date_of_birth)
            # concern-begin: refill-guard
            if result.get('status') == 'verified':
                if self.patient_id and self.patient_id != result['patient_id']:
                    result = {'status': 'not_verified', 'reason': 'already_verified_as_another_patient'}
                else:
                    self.patient_id = result['patient_id']
            # concern-end
            return clinic.for_model(result)
        def select_medication(medication_name: str):
            result = clinic.select_medication(self.cid, self.patient_id, medication_name)
            # concern-begin: refill-guard
            self.selected_id = result.get('record_id', '')
            self.selected_label = result.get('medication_label', '')
            # concern-end
            return result
        def send_refill_request(record_id: str, patient_note: str = ''):
            # concern-begin: refill-guard
            if not self.patient_id or not self.selected_id or record_id != self.selected_id:
                return {'status': 'not_sent', 'reason': 'unverified_or_wrong_entry'}
            # concern-end
            result = clinic.send_refill_request(self.cid, self.patient_id, self.selected_id, record_id, patient_note)
            return {**result, 'caller_answer': self.caller_answer}
        def check_request_status(submission_key: str):
            return clinic.check_request_status(self.cid, self.patient_id, submission_key)
        def route_clinical_question(question: str, record_id: str = ''):
            return clinic.route_clinical_question(self.cid, self.patient_id, question, record_id or None)
        return [Function(name=fn.__name__, entrypoint=fn,
                         description=clinic.TOOL_SPECS[fn.__name__]['description'],
                         parameters=clinic.json_schema(fn.__name__)['parameters'],
                         # concern-begin: refill-guard
                         requires_confirmation=fn.__name__ == 'send_refill_request')
                         # concern-end
                for fn in [verify_patient, select_medication, send_refill_request,
                           check_request_status, route_clinical_question]]

    async def turn(self, text: str) -> AsyncIterator[Say]:
        # concern-begin: refill-guard
        if self.pending is not None:
            pending, self.pending = self.pending, None
            self.caller_answer = text
            for requirement in pending.requirements or []:
                if not requirement.needs_confirmation:
                    continue
                call = requirement.tool_execution
                args = call.tool_args or {}
                allowed = bool(self.patient_id and self.selected_id and args.get('record_id') == self.selected_id)
                yes = allowed and caller_said_yes(text, self.selected_label)
                if allowed:
                    clinic.record_confirmation(self.cid, self.selected_id, yes,
                        mechanism='Agno native confirmation requirement; next caller turn',
                        question=clinic.confirmation_question(self.selected_label), answer=text)
                if yes:
                    requirement.confirm()
                else:
                    requirement.reject(note=text if allowed else 'Unverified patient or wrong medication entry')
                    yield Say('fixed', clinic.DECLINED_TEXT, 'declined')
            stream = self.agent.acontinue_run(run_id=pending.run_id, requirements=pending.requirements,
                                              session_id=self.cid, stream=True, stream_events=True)
        else:
        # concern-end
            prompt = ([Message(role='assistant', content=instructions.GREETING),
                       Message(role='user', content=text)] if self.first_turn else text)
            self.first_turn = False
            stream = self.agent.arun(prompt, session_id=self.cid, stream=True, stream_events=True)
        buffered = []
        async for event in stream:
            if isinstance(event, RunContentEvent) and isinstance(event.content, str):
                buffered.append(event.content)
                yield Say('delta', event.content)
            elif isinstance(event, ToolCallCompletedEvent) and event.tool:
                yield Say('tools', event.tool.tool_name or '', 'cancelled' if event.tool.tool_call_error else 'ok')
            elif isinstance(event, RunCompletedEvent):
                if buffered:
                    yield Say('end', ''.join(buffered))
                    buffered = []
            # concern-begin: refill-guard
            elif isinstance(event, RunPausedEvent):
                if buffered:
                    yield Say('end', ''.join(buffered))
                    buffered = []
                self.pending = event
                yield Say('fixed', clinic.confirmation_question(self.selected_label), 'confirmation')
            # concern-end
        if buffered:
            yield Say('end', ''.join(buffered))


CONVERSATIONS = {}


def conversation(cid):
    if cid not in CONVERSATIONS:
        CONVERSATIONS[cid] = Conversation(cid)
    return CONVERSATIONS[cid]
