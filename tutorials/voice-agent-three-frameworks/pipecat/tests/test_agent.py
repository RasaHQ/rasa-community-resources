import asyncio
import uuid
import unittest
from cedar_clinic import instructions, refills, tools as clinic
from cedar_clinic.audit import AUDIT
from pipecat.frames.frames import LLMTextFrame
from pipecat.services.openai.responses.llm import OpenAIResponsesHttpLLMService
from pipecat.services.llm_service import FunctionCallFromLLM
import agent

class ScriptedModel(OpenAIResponsesHttpLLMService):
    def __init__(self, outputs):
        super().__init__(api_key='offline-test', run_in_parallel=False)
        self.outputs = list(outputs)
    async def _process_context(self, context):
        value = self.outputs.pop(0) if self.outputs else 'Awaiting prescribing team review.'
        if isinstance(value, str):
            await self.push_frame(LLMTextFrame(value))
        else:
            name, args = value
            await self.run_function_calls([FunctionCallFromLLM(context=context,
                tool_call_id=uuid.uuid4().hex, function_name=name, arguments=args)])

class GuardTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        refills.reset_services(); AUDIT.clear()
        self.cid='pipecat-test-' + uuid.uuid4().hex; self.conversations=[]
    async def asyncTearDown(self):
        for c in self.conversations:
            await c.close()
    async def prepared(self):
        c=agent.Conversation(self.cid, llm=ScriptedModel([])); self.conversations.append(c)
        await c.execute('verify_patient', {'full_name':'Maria Alvarez','date_of_birth':'1968-03-14'})
        result=__import__('json').loads(await c.execute('select_medication', {'medication_name':'lisinopril'}))
        while not c.queue.empty(): c.queue.get_nowait()
        return c, result['record_id']
    async def collect(self,c,text):
        async def run(): return [s async for s in c.turn(text)]
        return await asyncio.wait_for(run(), 8)
    def effects(self): return sum(e['result'].get('effects',0) for e in AUDIT.entries(self.cid))
    async def test_native_function_runner_waits_for_confirmation(self):
        c, record=await self.prepared()
        c.llm.outputs=[('send_refill_request', {'record_id':record}), 'Awaiting team review.']
        said=await self.collect(c,'Send it')
        self.assertTrue(any(s.source=='confirmation' for s in said)); self.assertEqual(self.effects(),0)
        await self.collect(c,'Yes, please.'); self.assertEqual(self.effects(),1)
    async def test_correction_does_not_send(self):
        c, record=await self.prepared()
        c.llm.outputs=[('send_refill_request', {'record_id':record}), 'Which medicine?']
        await self.collect(c,'Send it'); await self.collect(c,'No, I meant budesonide.'); self.assertEqual(self.effects(),0)
    async def test_wrong_entry_is_refused(self):
        c, record=await self.prepared()
        c.llm.outputs=[('send_refill_request', {'record_id':'other'}), 'Please select a medicine.']
        await self.collect(c,'Send it'); self.assertEqual(self.effects(),0); self.assertIsNone(c.answer)
    async def test_contract_and_state(self):
        c, record=await self.prepared()
        self.assertEqual(agent.SYSTEM_PROMPT,instructions.system_prompt())
        self.assertEqual([s.to_default_dict() for s in c.schemas],[clinic.json_schema(n) for n in clinic.TOOL_SPECS])
        other=agent.Conversation(self.cid+'-other',llm=ScriptedModel([]))
        self.conversations.append(other); self.assertIsNone(other.patient_id)
