import asyncio
import json
import uuid
import unittest
from cedar_clinic import instructions, refills, tools as clinic
from cedar_clinic.audit import AUDIT
from livekit.agents import llm, DEFAULT_API_CONNECT_OPTIONS
import agent

class ScriptedStream(llm.LLMStream):
    async def _run(self):
        value=self._llm.outputs.pop(0) if self._llm.outputs else 'Awaiting prescribing team review.'
        if isinstance(value,str):
            delta=llm.ChoiceDelta(role='assistant',content=value)
        else:
            name,args=value
            delta=llm.ChoiceDelta(role='assistant',tool_calls=[llm.FunctionToolCall(name=name,
                arguments=json.dumps(args),call_id=uuid.uuid4().hex)])
        self._event_ch.send_nowait(llm.ChatChunk(id=uuid.uuid4().hex,delta=delta))

class ScriptedModel(llm.LLM):
    def __init__(self,outputs):
        super().__init__(); self.outputs=list(outputs)
    def chat(self,*,chat_ctx,tools=None,conn_options=DEFAULT_API_CONNECT_OPTIONS,**kwargs):
        return ScriptedStream(self,chat_ctx=chat_ctx,tools=tools or [],conn_options=conn_options)

class GuardTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        refills.reset_services(); AUDIT.clear()
        self.cid='livekit-test-'+uuid.uuid4().hex; self.conversations=[]
    async def asyncTearDown(self):
        for c in self.conversations: await c.close()
    async def prepared(self):
        c=agent.Conversation(self.cid,model=ScriptedModel([])); self.conversations.append(c)
        await c.execute('verify_patient',{'full_name':'Maria Alvarez','date_of_birth':'1968-03-14'})
        result=json.loads(await c.execute('select_medication',{'medication_name':'lisinopril'}))
        while not c.queue.empty(): c.queue.get_nowait()
        return c,result['record_id']
    async def collect(self,c,text):
        async def run(): return [s async for s in c.turn(text)]
        return await asyncio.wait_for(run(),8)
    def effects(self): return sum(e['result'].get('effects',0) for e in AUDIT.entries(self.cid))
    async def test_native_session_waits_for_confirmation(self):
        c,record=await self.prepared()
        c.model.outputs=[('send_refill_request',{'record_id':record}),'Awaiting team review.']
        said=await self.collect(c,'Send it')
        self.assertTrue(any(s.source=='confirmation' for s in said)); self.assertEqual(self.effects(),0)
        await self.collect(c,'Yes, please.'); self.assertEqual(self.effects(),1)
    async def test_correction_does_not_send(self):
        c,record=await self.prepared()
        c.model.outputs=[('send_refill_request',{'record_id':record}),'Which medicine?']
        await self.collect(c,'Send it'); await self.collect(c,'No, I meant budesonide.'); self.assertEqual(self.effects(),0)
    async def test_wrong_entry_is_refused(self):
        c,record=await self.prepared()
        c.model.outputs=[('send_refill_request',{'record_id':'other'}),'Please select a medicine.']
        await self.collect(c,'Send it'); self.assertEqual(self.effects(),0); self.assertIsNone(c.answer)
    async def test_common_prompt_and_schemas(self):
        c,record=await self.prepared()
        self.assertEqual(c.agent.instructions,instructions.system_prompt())
        self.assertEqual([__import__("livekit.agents.llm.tool_context", fromlist=["get_raw_function_info"]).get_raw_function_info(t).raw_schema for t in c.tools],
            [clinic.json_schema(n) for n in clinic.TOOL_SPECS])
    async def test_hangup_cancels_pending_confirmation(self):
        c,record=await self.prepared()
        c.model.outputs=[('send_refill_request',{'record_id':record}),'Call ended.']
        await self.collect(c,'Send it'); await c.close(); self.assertEqual(self.effects(),0)
