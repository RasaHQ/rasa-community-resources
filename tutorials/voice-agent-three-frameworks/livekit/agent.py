# concern: agent-logic
"""Local LiveKit Agents session; no room, Cloud inference or managed deployment."""
from __future__ import annotations
import asyncio
import json
import os
from dataclasses import dataclass
from cedar_clinic import instructions, tools as clinic
from guard import caller_said_yes
from livekit.agents import Agent, AgentSession, llm
from livekit.agents.voice import io
from livekit.plugins.openai.responses import LLM
from openai.types.shared import Reasoning

SYSTEM_PROMPT = instructions.system_prompt()
MODEL_ID = os.environ.get('CEDAR_MODEL', 'gpt-5.5-2026-04-23')

@dataclass
class Say:
    kind: str
    text: str = ''
    source: str = 'model'

class TextOutput(io.TextOutput):
    def __init__(self, owner):
        super().__init__(label='cedar-browser', next_in_chain=None)
        self.owner = owner
        self.text = ''
    async def capture_text(self, text):
        self.text += text
        self.owner.queue.put_nowait(Say('delta', text))
    def flush(self):
        if self.text:
            self.owner.queue.put_nowait(Say('end', self.text))
            self.text = ''

class Conversation:
    def __init__(self, cid, model=None):
        self.cid = cid
        self.queue = asyncio.Queue()
        # concern-begin: refill-guard
        self.answer = None
        self.patient_id = None
        self.selected_id = ''
        self.selected_label = ''
        self.closed = False
        # concern-end
        self.started = False
        self.task = None
        self.model = model if model is not None else LLM(model=MODEL_ID,
            base_url=os.environ.get('OPENAI_BASE_URL') or 'https://api.openai.com/v1',
            use_websocket=False, reasoning=Reasoning(effort='low'),
            store=False, parallel_tool_calls=False)
        self.tools = [self.make_tool(name) for name in clinic.TOOL_SPECS]
        context = llm.ChatContext()
        context.add_message(role='assistant', content=instructions.GREETING)
        self.agent = Agent(instructions=SYSTEM_PROMPT, tools=self.tools, chat_ctx=context)
        self.session = None

    def make_tool(self, name):
        async def handler(raw_arguments: dict[str, object]):
            return json.loads(await self.execute(name, raw_arguments))
        handler.__name__ = name
        return llm.function_tool(handler, raw_schema=clinic.json_schema(name), on_duplicate='allow')

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
                mechanism='LiveKit application tool future; next caller turn',
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


    async def start(self):
        if not self.started:
            self.session = AgentSession(llm=self.model, max_tool_steps=30,
                turn_handling={'turn_detection':'manual', 'interruption':{'enabled':False}}, user_away_timeout=None)
            self.session.output.transcription = TextOutput(self)
            await self.session.start(self.agent, record=False)
            self.started = True

    async def _run(self, text):
        try:
            handle = self.session.generate_reply(user_input=text, allow_interruptions=False)
            await handle
            if handle.exception():
                raise handle.exception()
        except asyncio.CancelledError:
            raise
        except Exception as error:
            self.queue.put_nowait(error)
        finally:
            self.queue.put_nowait(None)

    async def turn(self, text):
        if self.closed:
            raise RuntimeError('Call is closed')
        await self.start()
        # concern-begin: refill-guard
        if self.answer is not None:
            if self.answer.done():
                raise RuntimeError('Confirmation already answered')
            self.answer.set_result(text)
        else:
        # concern-end
            self.task = asyncio.create_task(self._run(text))
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
            self.answer.cancel()
        if self.session:
            await self.session.aclose()
        if self.task:
            self.task.cancel()
            await asyncio.gather(self.task, return_exceptions=True)

CONVERSATIONS = {}
def conversation(cid):
    if cid not in CONVERSATIONS:
        CONVERSATIONS[cid] = Conversation(cid)
    return CONVERSATIONS[cid]
