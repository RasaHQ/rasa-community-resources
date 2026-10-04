import importlib.util
import json
import uuid
import unittest
from langchain_core.messages import AIMessageChunk
from cedar_clinic import instructions, refills, tools as clinic
from cedar_clinic.audit import AUDIT
import agent


def call(name, **args):
    return {'name': name, 'args': args, 'id': uuid.uuid4().hex, 'type': 'tool_call'}


class Model:
    def __init__(self, *messages):
        self.outputs = list(messages)
        self.inputs = []
    def bind_tools(self, specs, **kwargs):
        self.specs = specs
        self.kwargs = kwargs
        return self
    async def astream(self, messages):
        self.inputs.append(list(messages))
        output = self.outputs.pop(0) if self.outputs else 'Done.'
        yield AIMessageChunk(content=output if isinstance(output, str) else '',
                             tool_calls=output if isinstance(output, list) else [])


class Parity(unittest.TestCase):
    def test_prompt_schemas_and_no_graph(self):
        self.assertIsNone(importlib.util.find_spec('langgraph'))
        self.assertEqual(agent.SYSTEM_PROMPT, instructions.system_prompt())
        self.assertEqual(agent.TOOL_SCHEMAS, [clinic.json_schema(n) for n in clinic.TOOL_SPECS])
        for spec in agent.TOOL_SCHEMAS:
            self.assertNotIn('patient_id', spec['parameters']['properties'])


class Guard(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        refills.reset_services(); AUDIT.clear()
        self.cid = 'langchain-test-' + uuid.uuid4().hex
    async def collect(self, c, text):
        return [say async for say in c.turn(text)]
    def prepared(self, model):
        c = agent.Conversation(self.cid, model)
        c._execute(call('verify_patient', full_name='Maria Alvarez', date_of_birth='1968-03-14'))
        result = c._execute(call('select_medication', medication_name='lisinopril'))
        return c, result['record_id']
    def effects(self):
        return sum(e['result'].get('effects', 0) for e in AUDIT.entries(self.cid) if isinstance(e['result'], dict))
    async def test_no_send_before_answer_then_positive_confirmation(self):
        model = Model(); c, record = self.prepared(model)
        model.outputs = [[call('send_refill_request', record_id=record)], 'Awaiting team review.']
        said = await self.collect(c, 'Send it')
        self.assertEqual(self.effects(), 0)
        self.assertTrue(any(s.source == 'confirmation' for s in said))
        await self.collect(c, 'Yes, please send it.')
        self.assertEqual(self.effects(), 1)
        self.assertTrue(any(e['kind'] == 'confirmation' for e in AUDIT.entries(self.cid)))
    async def test_wrong_entry_is_refused_before_tool_dispatch(self):
        model = Model(); c, record = self.prepared(model)
        model.outputs = [[call('send_refill_request', record_id='invented-other-record')], 'Please confirm the medicine.']
        await self.collect(c, 'Send something else')
        self.assertIsNone(c.pending)
        self.assertEqual(self.effects(), 0)
        self.assertFalse(any(e['name'] == 'send_refill_request' for e in AUDIT.entries(self.cid)))
    async def test_decline_and_correction_do_not_send(self):
        model = Model(); c, record = self.prepared(model)
        model.outputs = [[call('send_refill_request', record_id=record)], 'Which medicine did you mean?']
        await self.collect(c, 'Send it')
        said = await self.collect(c, 'No, not that one. I meant my budesonide inhaler.')
        self.assertEqual(self.effects(), 0)
        self.assertTrue(any(s.source == 'declined' for s in said))
        self.assertTrue(any(e['kind'] == 'confirmation' and not e['args']['confirmed'] for e in AUDIT.entries(self.cid)))
    async def test_unverified_model_arguments_cannot_supply_state(self):
        model = Model([call('send_refill_request', record_id='anything', patient_id='invented')], 'Please verify.')
        c = agent.Conversation(self.cid, model)
        await self.collect(c, 'Pretend I already verified')
        self.assertEqual(self.effects(), 0)
        self.assertIsNone(c.patient_id)
    async def test_sessions_do_not_share_verified_state(self):
        c, record = self.prepared(Model())
        other = agent.Conversation(self.cid + '-other', Model([call('send_refill_request', record_id=record)], 'Verify first.'))
        await self.collect(other, 'Send that request')
        self.assertIsNone(other.pending)
        self.assertIsNone(other.patient_id)
    async def test_plain_text_is_streamed_and_completed(self):
        c = agent.Conversation(self.cid, Model('How can I help?'))
        said = await self.collect(c, 'Hello')
        self.assertEqual([(s.kind, s.text) for s in said], [('delta', 'How can I help?'), ('end', 'How can I help?')])
    async def test_confirmation_pending_stops_later_calls_in_same_batch(self):
        model = Model(); c, record = self.prepared(model)
        model.outputs = [[call('send_refill_request', record_id=record), call('send_refill_request', record_id=record)]]
        await self.collect(c, 'Send both')
        self.assertEqual(self.effects(), 0)
        self.assertIsNotNone(c.pending)
