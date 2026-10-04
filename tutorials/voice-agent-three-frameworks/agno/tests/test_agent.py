import json
import uuid
import unittest
from agno.models.base import Model
from agno.models.response import ModelResponse
from cedar_clinic import instructions, refills, tools as clinic
from cedar_clinic.audit import AUDIT
import agent


class ScriptedModel(Model):
    def __init__(self, outputs):
        super().__init__(id='offline', provider='test')
        self.outputs = list(outputs)
    def invoke(self, **kwargs):
        return self.next()
    async def ainvoke(self, **kwargs):
        return self.next()
    def invoke_stream(self, **kwargs):
        yield self.next()
    async def ainvoke_stream(self, **kwargs):
        yield self.next()
    def _parse_provider_response(self, response, **kwargs):
        return response
    def _parse_provider_response_delta(self, response):
        return response
    def next(self):
        value = self.outputs.pop(0) if self.outputs else 'Awaiting prescribing team review.'
        if isinstance(value, str):
            return ModelResponse(role='assistant', content=value)
        name, args = value
        return ModelResponse(role='assistant', tool_calls=[{'index': 0, 'id': uuid.uuid4().hex,
            'type': 'function', 'function': {'name': name, 'arguments': json.dumps(args)}}])


class NativeGuardTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        refills.reset_services(); AUDIT.clear(); self.cid = 'agno-test-' + uuid.uuid4().hex
    def prepared(self):
        c = agent.Conversation(self.cid, ScriptedModel([]))
        functions = {f.name: f.entrypoint for f in c.tools}
        functions['verify_patient']('Maria Alvarez', '1968-03-14')
        selected = functions['select_medication']('lisinopril')
        return c, selected['record_id']
    async def collect(self, c, text):
        return [s async for s in c.turn(text)]
    def effects(self):
        return sum(e['result'].get('effects', 0) for e in AUDIT.entries(self.cid))
    async def test_native_pause_resume_requires_a_later_caller_turn(self):
        c, record = self.prepared()
        c.agent.model.outputs = [('send_refill_request', {'record_id': record}), 'Awaiting team review.']
        said = await self.collect(c, 'Please send it')
        self.assertEqual(self.effects(), 0)
        self.assertIsNotNone(c.pending)
        self.assertTrue(any(s.source == 'confirmation' for s in said))
        await self.collect(c, 'Yes, please.')
        self.assertEqual(self.effects(), 1)
    async def test_native_rejection_does_not_send(self):
        c, record = self.prepared()
        c.agent.model.outputs = [('send_refill_request', {'record_id': record}), 'Which medicine instead?']
        await self.collect(c, 'Send it')
        await self.collect(c, 'No, I meant budesonide.')
        self.assertEqual(self.effects(), 0)
        self.assertTrue(any(e['kind'] == 'confirmation' and not e['args']['confirmed'] for e in AUDIT.entries(self.cid)))
    async def test_wrong_record_stays_blocked_despite_yes(self):
        c, record = self.prepared()
        c.agent.model.outputs = [('send_refill_request', {'record_id': 'another-entry'}), 'Please select a medicine.']
        await self.collect(c, 'Send it')
        await self.collect(c, 'Yes')
        self.assertEqual(self.effects(), 0)
    def test_prompt_and_tool_schemas_are_the_shared_contract(self):
        c, _ = self.prepared()
        self.assertEqual(agent.SYSTEM_PROMPT, instructions.system_prompt())
        self.assertEqual({f.name: {'name': f.name, 'description': f.description, 'parameters': f.parameters} for f in c.tools},
                         {n: clinic.json_schema(n) for n in clinic.TOOL_SPECS})
        self.assertTrue(next(f for f in c.tools if f.name == 'send_refill_request').requires_confirmation)
    def test_selected_state_is_private_and_per_conversation(self):
        c, record = self.prepared(); other = agent.Conversation(self.cid + '-other', ScriptedModel([]))
        self.assertIsNone(other.patient_id)
        self.assertEqual(other.selected_id, '')
        self.assertFalse(c.agent.add_session_state_to_context)
