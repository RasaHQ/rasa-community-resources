# concern: agent-logic
"""A local single CrewAI agent; tool confirmation is application-side code."""
from __future__ import annotations
import asyncio
import copy
import json
import os
from dataclasses import dataclass
from typing import Any, Callable

os.environ['CREWAI_TELEMETRY_DISABLED'] = 'true'
os.environ['OTEL_SDK_DISABLED'] = 'true'
from crewai import Agent
from crewai.llms.providers.openai.completion import OpenAICompletion
from crewai.tools import BaseTool
from pydantic import BaseModel, ConfigDict, Field, create_model
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


def argument_model(name):
    schema = clinic.json_schema(name)['parameters']
    class ClinicArguments(BaseModel):
        model_config = ConfigDict(extra="forbid")
        @classmethod
        def model_json_schema(cls, *args, **kwargs):
            return copy.deepcopy(schema)
    fields = {}
    for key, spec in schema['properties'].items():
        default = ... if key in schema.get('required', []) else spec.get('default', '')
        fields[key] = (str, Field(default=default, description=spec.get('description', '')))
    return create_model(name + '_arguments', __base__=ClinicArguments, **fields)


class ClinicResponses(OpenAICompletion):
    def _convert_tools_for_responses(self, tools):
        # CrewAI's schema conversion makes optional fields required. Preserve
        # the pinned clinic contract at the actual provider boundary.
        converted = super()._convert_tools_for_responses(tools)
        for tool in converted:
            spec = clinic.json_schema(tool['name'])
            tool.update(description=spec['description'], parameters=spec['parameters'], strict=False)
        return converted

class ClinicTool(BaseTool):
    handler: Callable = Field(exclude=True)
    def _run(self, **kwargs):
        return self.handler(self.name, kwargs)
    async def _arun(self, **kwargs):
        return await asyncio.to_thread(self.handler, self.name, kwargs)


class Conversation:
    def __init__(self, cid, llm=None):
        self.cid = cid
        self.messages = [{'role': 'assistant', 'content': instructions.GREETING}]
        self.queue = asyncio.Queue()
        self.task = None
        self.loop = None
        self.closed = False
        # concern-begin: refill-guard
        self.patient_id = None
        self.selected_id = ''
        self.selected_label = ''
        self.answer = None
        # concern-end
        self.tools = [ClinicTool(name=name, description=spec['description'],
                                 args_schema=argument_model(name), handler=self.execute_from_worker)
                      for name, spec in clinic.TOOL_SPECS.items()]
        # BaseTool adds a display wrapper; the provider gets the shared description.
        for tool in self.tools:
            tool.description = clinic.TOOL_SPECS[tool.name]["description"]
        self.agent = Agent(role=instructions.PERSONA,
                           goal='Handle the caller under the shared Cedar Clinic procedure.',
                           backstory=SYSTEM_PROMPT, tools=self.tools,
                           llm=llm if llm is not None else ClinicResponses(model=MODEL_ID, api='responses',
                            reasoning_effort='low', store=False, parallel_tool_calls=False, base_url=os.environ.get('OPENAI_BASE_URL')),
                           allow_delegation=False, verbose=False, cache=False, max_iter=30)

    def execute_from_worker(self, name, args):
        if self.loop is None:
            raise RuntimeError("Agent worker has no voice event loop")
        return asyncio.run_coroutine_threadsafe(self.execute(name, args), self.loop).result()

    async def execute(self, name, args):
        if self.closed:
            return json.dumps({"status": "not_sent", "reason": "call_closed"})
        if name == 'verify_patient':
            result = clinic.verify_patient(self.cid, args['full_name'], args['date_of_birth'])
            # concern-begin: refill-guard
            if result.get('status') == 'verified':
                if self.patient_id and self.patient_id != result['patient_id']:
                    result = {'status': 'not_verified', 'reason': 'already_verified_as_another_patient'}
                else:
                    self.patient_id = result['patient_id']
            # concern-end
            result = clinic.for_model(result)
        elif name == 'select_medication':
            result = clinic.select_medication(self.cid, self.patient_id, args['medication_name'])
            # concern-begin: refill-guard
            self.selected_id = result.get('record_id', '')
            self.selected_label = result.get('medication_label', '')
            # concern-end
        elif name == 'send_refill_request':
            # concern-begin: refill-guard
            if not self.patient_id or not self.selected_id or args.get('record_id') != self.selected_id:
                return json.dumps({'status': 'not_sent', 'reason': 'unverified_or_wrong_entry'})
            if self.answer is not None:
                return json.dumps({'status': 'not_sent', 'reason': 'another_confirmation_pending'})
            self.answer = asyncio.get_running_loop().create_future()
            self.queue.put_nowait(Say('fixed', clinic.confirmation_question(self.selected_label), 'confirmation'))
            try:
                answer = await self.answer
            finally:
                self.answer = None
            yes = caller_said_yes(answer, self.selected_label)
            clinic.record_confirmation(self.cid, self.selected_id, yes,
                mechanism='CrewAI application tool future; next caller turn',
                question=clinic.confirmation_question(self.selected_label), answer=answer)
            if not yes:
                self.queue.put_nowait(Say('fixed', clinic.DECLINED_TEXT, 'declined'))
                return json.dumps({'status': 'not_sent', 'reason': 'confirmation_declined', 'caller_answer': answer})
            # concern-end
            result = {**clinic.send_refill_request(self.cid, self.patient_id, self.selected_id,
                      args['record_id'], args.get('patient_note', '')), 'caller_answer': answer}
        elif name == 'check_request_status':
            result = clinic.check_request_status(self.cid, self.patient_id, args['submission_key'])
        elif name == 'route_clinical_question':
            result = clinic.route_clinical_question(self.cid, self.patient_id, args['question'], args.get('record_id') or None)
        else:
            raise ValueError('Unknown clinic tool')
        self.queue.put_nowait(Say('tools', name, 'ok'))
        return json.dumps(result)

    async def _run(self):
        try:
            output = await asyncio.to_thread(self.agent.kickoff, self.messages)
            self.messages = list(output.messages)
            self.queue.put_nowait(Say('delta', output.raw))
            self.queue.put_nowait(Say('end', output.raw))
        except asyncio.CancelledError:
            raise
        except Exception as error:
            self.queue.put_nowait(error)
        finally:
            self.queue.put_nowait(None)

    async def turn(self, text):
        self.loop = asyncio.get_running_loop()
        if self.closed:
            raise RuntimeError("Call is closed")
        # concern-begin: refill-guard
        if self.answer is not None:
            if self.answer.done():
                raise RuntimeError('Confirmation answer already supplied')
            self.answer.set_result(text)
        else:
        # concern-end
            self.messages.append({'role': 'user', 'content': text})
            self.task = asyncio.create_task(self._run())
        while True:
            item = await self.queue.get()
            if item is None:
                return
            if isinstance(item, Exception):
                raise item
            yield item
            # concern-begin: refill-guard
            if item.source == 'confirmation':
                return
            # concern-end

    async def close(self):
        self.closed = True
        if self.answer is not None and not self.answer.done():
            self.answer.set_result("No, the call has ended.")
        if self.task and not self.task.done():
            self.task.cancel()
            await asyncio.gather(self.task, return_exceptions=True)


CONVERSATIONS = {}


def conversation(cid):
    if cid not in CONVERSATIONS:
        CONVERSATIONS[cid] = Conversation(cid)
    return CONVERSATIONS[cid]
