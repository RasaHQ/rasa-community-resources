# concern: agent-logic
"""Native Pipecat Responses service, function runner and conversation aggregation."""
from __future__ import annotations
import asyncio
import json
import os
from dataclasses import dataclass
from cedar_clinic import instructions, tools as clinic
from guard import caller_said_yes
from pipecat.adapters.schemas.function_schema import FunctionSchema
from pipecat.adapters.schemas.tools_schema import ToolsSchema
from pipecat.frames.frames import (LLMContextFrame, LLMTextFrame,
    LLMFullResponseStartFrame, LLMFullResponseEndFrame, ErrorFrame)
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.worker import PipelineWorker, PipelineParams
from pipecat.workers.runner import WorkerRunner
from pipecat.processors.frame_processor import FrameProcessor
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import LLMAssistantAggregator
from pipecat.services.openai.responses.llm import OpenAIResponsesHttpLLMService, OpenAIResponsesReasoningConfig

SYSTEM_PROMPT = instructions.system_prompt()
MODEL_ID = os.environ.get('CEDAR_MODEL', 'gpt-5.5-2026-04-23')

@dataclass
class Say:
    kind: str
    text: str = ''
    source: str = 'model'

class ClinicSchema(FunctionSchema):
    def to_default_dict(self):
        return clinic.json_schema(self._name)

class Output(FrameProcessor):
    def __init__(self, owner):
        super().__init__(); self.owner = owner; self.text = ''
    async def process_frame(self, frame, direction):
        await super().process_frame(frame, direction)
        if isinstance(frame, LLMFullResponseStartFrame):
            self.text = ''
        elif isinstance(frame, LLMTextFrame):
            self.text += frame.text
            self.owner.queue.put_nowait(Say('delta', frame.text))
        elif isinstance(frame, LLMFullResponseEndFrame) and self.text:
            self.owner.queue.put_nowait(Say('end', self.text))
            self.owner.queue.put_nowait(None)
        elif isinstance(frame, ErrorFrame):
            self.owner.queue.put_nowait(RuntimeError(frame.error))
        await self.push_frame(frame, direction)

class Conversation:
    def __init__(self, cid, llm=None):
        self.cid = cid
        self.queue = asyncio.Queue()
        # concern-begin: refill-guard
        self.answer = None
        self.patient_id = None
        self.selected_id = ''
        self.selected_label = ''
        self.closed = False
        # concern-end
        self.running = None
        self.schemas = [ClinicSchema(name=s['name'], description=s['description'],
            properties=s['parameters']['properties'], required=s['parameters'].get('required', []))
            for s in (clinic.json_schema(n) for n in clinic.TOOL_SPECS)]
        self.context = LLMContext(messages=[{'role':'system', 'content': SYSTEM_PROMPT},
            {'role':'assistant', 'content': instructions.GREETING}], tools=ToolsSchema(standard_tools=self.schemas))
        self.llm = llm if llm is not None else OpenAIResponsesHttpLLMService(
            api_key=os.environ.get('OPENAI_API_KEY'), base_url=os.environ.get('OPENAI_BASE_URL'),
            run_in_parallel=False, settings=OpenAIResponsesHttpLLMService.Settings(
                model=MODEL_ID, reasoning=OpenAIResponsesReasoningConfig(effort='low'),
                extra={'store':False, 'parallel_tool_calls':False}))
        for name in clinic.TOOL_SPECS:
            self.llm.register_function(name, self.handle_tool, cancel_on_interruption=False)
        self.aggregator = LLMAssistantAggregator(self.context)
        self.output = Output(self)
        self.worker = PipelineWorker(Pipeline([self.llm, self.output, self.aggregator]),
            params=PipelineParams(audio_in_sample_rate=24000, audio_out_sample_rate=24000),
            app_resources=self, enable_rtvi=False, idle_timeout_secs=None)
        self.runner = None

    async def handle_tool(self, params):
        result = json.loads(await self.execute(params.function_name, dict(params.arguments)))
        await params.result_callback(result)

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
                mechanism='Pipecat application tool future; next caller turn',
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


    async def turn(self, text):
        if self.closed:
            raise RuntimeError('Call is closed')
        if self.running is None:
            self.runner = WorkerRunner(handle_sigint=False, handle_sigterm=False)
            await self.runner.add_workers(self.worker)
            self.running = asyncio.create_task(self.runner.run())
        # concern-begin: refill-guard
        if self.answer is not None:
            if self.answer.done():
                raise RuntimeError('Confirmation already answered')
            self.answer.set_result(text)
        else:
        # concern-end
            self.context.add_message({'role':'user', 'content':text})
            await self.worker.queue_frame(LLMContextFrame(self.context))
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
        if self.running:
            await self.worker.cancel()
            await asyncio.gather(self.running, return_exceptions=True)

CONVERSATIONS = {}
def conversation(cid):
    if cid not in CONVERSATIONS:
        CONVERSATIONS[cid] = Conversation(cid)
    return CONVERSATIONS[cid]
