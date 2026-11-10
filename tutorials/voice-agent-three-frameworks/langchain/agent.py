# concern: agent-logic
"""An explicit LangChain model/tool loop with no LangGraph dependency.

The model-facing tool schemas and instructions come unchanged from the
shared clinic. The application owns history, execution, private state and
pause/resume. This is deliberately not LangChain's graph-backed create_agent.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import AsyncIterator

from cedar_clinic import instructions
from cedar_clinic import tools as clinic
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.messages import message_chunk_to_message
from langchain_openai import ChatOpenAI

from guard import caller_said_yes

MODEL_ID = os.environ.get('CEDAR_MODEL', 'gpt-5.5-2026-04-23')
SYSTEM_PROMPT = instructions.system_prompt()
TOOL_SCHEMAS = [clinic.json_schema(name) for name in clinic.TOOL_SPECS]


@dataclass
class Say:
    kind: str
    text: str = ''
    source: str = 'model'


def make_model():
    return ChatOpenAI(model=MODEL_ID, reasoning_effort='low', use_responses_api=True,
                      output_version='responses/v1', streaming=True, store=False)


def content_text(content):
    if isinstance(content, str):
        return content
    return ''.join(b.get('text', '') for b in content if isinstance(b, dict) and b.get('type') == 'text')


class Conversation:
    def __init__(self, conversation_id: str, model=None):
        self.cid = conversation_id
        self.model = (model if model is not None else make_model()).bind_tools(
            TOOL_SCHEMAS, parallel_tool_calls=False)
        self.messages = [SystemMessage(SYSTEM_PROMPT), AIMessage(instructions.GREETING)]
        # concern-begin: refill-guard
        self.patient_id = None
        self.selected_id = ''
        self.selected_label = ''
        self.pending = None
        # concern-end

    def _reply(self, call, result):
        return ToolMessage(json.dumps(result), tool_call_id=call['id'], name=call['name'])

    def _execute(self, call):
        args, name = call['args'], call['name']
        if name == 'verify_patient':
            result = clinic.verify_patient(self.cid, args['full_name'], args['date_of_birth'])
            # concern-begin: refill-guard
            if result.get('status') == 'verified':
                if self.patient_id and self.patient_id != result['patient_id']:
                    result = {'status': 'not_verified', 'reason': 'already_verified_as_another_patient'}
                else:
                    self.patient_id = result['patient_id']
            # concern-end
            return clinic.for_model(result)
        if name == 'select_medication':
            result = clinic.select_medication(self.cid, self.patient_id, args['medication_name'])
            # concern-begin: refill-guard
            self.selected_id = result.get('record_id', '')
            self.selected_label = result.get('medication_label', '')
            # concern-end
            return result
        if name == 'send_refill_request':
            return clinic.send_refill_request(self.cid, self.patient_id, self.selected_id,
                                              args['record_id'], args.get('patient_note', ''))
        if name == 'check_request_status':
            return clinic.check_request_status(self.cid, self.patient_id, args['submission_key'])
        if name == 'route_clinical_question':
            return clinic.route_clinical_question(self.cid, self.patient_id, args['question'],
                                                   args.get('record_id') or None)
        return {'status': 'error', 'reason': 'unknown_tool'}

    async def turn(self, text: str) -> AsyncIterator[Say]:
        # concern-begin: refill-guard
        if self.pending:
            call = self.pending
            self.pending = None
            approved = caller_said_yes(text, self.selected_label)
            clinic.record_confirmation(self.cid, call['args']['record_id'], approved,
                                       mechanism='LangChain application pause; next caller turn',
                                       question=clinic.confirmation_question(self.selected_label), answer=text)
            result = self._execute(call) if approved else {
                'status': 'not_sent', 'reason': 'confirmation_declined', 'caller_answer': text}
            self.messages.append(self._reply(call, result))
            if not approved:
                yield Say('fixed', clinic.DECLINED_TEXT, 'declined')
            yield Say('tools', call['name'], 'ok' if approved else 'cancelled')
        # concern-end
        self.messages.append(HumanMessage(text))
        # A finite cap fails explicitly; a stopped loop must not look like success.
        for _ in range(30):
            accumulated = None
            parts = []
            async for chunk in self.model.astream(self.messages):
                accumulated = chunk if accumulated is None else accumulated + chunk
                value = content_text(chunk.content)
                if value:
                    parts.append(value)
                    yield Say('delta', value)
            if accumulated is None:
                raise RuntimeError('Model returned no message')
            message = message_chunk_to_message(accumulated)
            self.messages.append(message)
            if parts:
                yield Say('end', ''.join(parts))
            if not message.tool_calls:
                return
            paused = False
            for call in message.tool_calls:
                # concern-begin: refill-guard
                if paused:
                    self.messages.append(self._reply(call, {'status': 'not_run', 'reason': 'confirmation_pending'}))
                    continue
                if call['name'] == 'send_refill_request':
                    if not self.patient_id or not self.selected_id or call['args'].get('record_id') != self.selected_id:
                        self.messages.append(self._reply(call, {'status': 'not_sent', 'reason': 'unverified_or_wrong_entry'}))
                        yield Say('tools', call['name'], 'cancelled')
                        continue
                    self.pending = call
                    paused = True
                    yield Say('fixed', clinic.confirmation_question(self.selected_label), 'confirmation')
                    continue
                # concern-end
                self.messages.append(self._reply(call, self._execute(call)))
                yield Say('tools', call['name'], 'ok')
            if paused:
                return
        raise RuntimeError('Model/tool iteration limit exceeded')


CONVERSATIONS = {}


def conversation(cid):
    if cid not in CONVERSATIONS:
        CONVERSATIONS[cid] = Conversation(cid)
    return CONVERSATIONS[cid]
