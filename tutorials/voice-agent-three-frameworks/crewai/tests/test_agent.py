import asyncio
import json
import uuid
import unittest
from pydantic import PrivateAttr
from crewai.llms.base_llm import BaseLLM
from cedar_clinic import instructions, refills, tools as clinic
from cedar_clinic.audit import AUDIT
import agent


class ScriptedModel(BaseLLM):
    _outputs: list = PrivateAttr(default_factory=list)
    def __init__(self, outputs):
        super().__init__(model='offline')
        self._outputs = list(outputs)
    def supports_function_calling(self):
        return True
    def call(self, messages, **kwargs):
        value = self._outputs.pop(0) if self._outputs else 'Awaiting prescribing team review.'
        if isinstance(value, str):
            return value
        name, args = value
        return [{'id': uuid.uuid4().hex, 'type': 'function',
                 'function': {'name': name, 'arguments': json.dumps(args)}}]
    async def acall(self, messages, **kwargs):
        return self.call(messages, **kwargs)


class GuardTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        refills.reset_services(); AUDIT.clear()
        self.cid = 'crewai-test-' + uuid.uuid4().hex
        self.conversations = []
    async def asyncTearDown(self):
        for c in self.conversations:
            await c.close()
    async def prepared(self):
        c = agent.Conversation(self.cid, llm=ScriptedModel([]))
        self.conversations.append(c)
        await c.execute('verify_patient', {'full_name': 'Maria Alvarez', 'date_of_birth': '1968-03-14'})
        result = json.loads(await c.execute('select_medication', {'medication_name': 'lisinopril'}))
        while not c.queue.empty():
            c.queue.get_nowait()
        return c, result['record_id']
    async def collect(self, c, text):
        return await asyncio.wait_for(self._collect(c, text), 8)
    async def _collect(self, c, text):
        return [s async for s in c.turn(text)]
    def effects(self):
        return sum(e['result'].get('effects', 0) for e in AUDIT.entries(self.cid))
    async def test_native_agent_waits_for_later_confirmation(self):
        c, record = await self.prepared()
        c.agent.llm._outputs = [('send_refill_request', {'record_id': record}), 'Awaiting team review.']
        said = await self.collect(c, 'Send it')
        self.assertTrue(any(s.source == 'confirmation' for s in said))
        self.assertEqual(self.effects(), 0)
        self.assertFalse(c.task.done())
        await self.collect(c, 'Yes, please.')
        self.assertEqual(self.effects(), 1)
    async def test_correction_does_not_send(self):
        c, record = await self.prepared()
        c.agent.llm._outputs = [('send_refill_request', {'record_id': record}), 'Which medicine?']
        await self.collect(c, 'Send it')
        await self.collect(c, 'No, I meant budesonide.')
        self.assertEqual(self.effects(), 0)
    async def test_wrong_record_cannot_send(self):
        c, record = await self.prepared()
        c.agent.llm._outputs = [('send_refill_request', {'record_id': 'other'}), 'Please select a medicine.']
        await self.collect(c, 'Send it')
        self.assertEqual(self.effects(), 0)
        self.assertIsNone(c.answer)
    async def test_hangup_releases_confirmation_without_sending(self):
        c, record = await self.prepared()
        c.agent.llm._outputs = [('send_refill_request', {'record_id': record}), 'Call ended.']
        await self.collect(c, 'Send it')
        await c.close()
        await asyncio.sleep(.05)
        self.assertEqual(self.effects(), 0)
        self.assertTrue(c.closed)
        self.assertEqual(json.loads(await c.execute('send_refill_request', {'record_id': record}))['reason'], 'call_closed')
    async def test_common_prompt_and_private_state(self):
        c, record = await self.prepared()
        self.assertEqual(c.agent.backstory, instructions.system_prompt())
        self.assertFalse(c.agent.allow_delegation)
        self.assertFalse(c.agent.cache)
        for tool in c.tools:
            expected = clinic.json_schema(tool.name)['parameters']
            actual = tool.args_schema.model_json_schema()
            self.assertEqual(actual.get('required'), expected.get('required'))
            self.assertFalse(actual['additionalProperties'])
            self.assertEqual(actual, expected)
            self.assertEqual(tool.description, clinic.json_schema(tool.name)['description'])
            self.assertNotIn('patient_id', actual['properties'])
