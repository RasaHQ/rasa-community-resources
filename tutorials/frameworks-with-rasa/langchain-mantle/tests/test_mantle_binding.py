"""Actual decorated Mantle tools and native LangChain retrieval; no model conversation."""
import importlib.util
import inspect
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from policy_worker.handoff import PolicySession

class MantlePolicyBindings(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        path=Path(__file__).resolve().parents[1]/'skills/card_policy/tools.py'
        spec=importlib.util.spec_from_file_location('policy_tools',path)
        self.tools=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.tools)

    async def test_native_signature_does_not_offer_scope(self):
        self.assertEqual(set(inspect.signature(self.tools.retrieve_card_policy).parameters),{'question','context'})

    async def test_native_tool_refuses_missing_demo(self):
        with patch.object(self.tools,'session',return_value=PolicySession()):
            result=await self.tools.retrieve_card_policy('Replace card')
        self.assertEqual(result.llm_response,{'status':'needs_demo_code'})

    async def test_actual_native_retriever_reached_through_mantle_tool(self):
        with patch.object(self.tools,'session',return_value=PolicySession()):
            await self.tools.select_policy_demo('111111')
            result=await self.tools.retrieve_card_policy('Replace card')
        self.assertEqual(result.llm_response['sources'][0]['id'],'P-101')
        self.assertNotIn('answer',result.llm_response)
        self.assertEqual(set(result.llm_response['sources'][0]),{'id','revision','quote'})

    async def test_factory_separates_two_sender_contexts(self):
        native='rasa.mantle.orchestration.turn_context.current_turn_context'
        with patch(native,return_value=SimpleNamespace(sender_id='demo-sender-a')):
            await self.tools.select_policy_demo('111111')
        with patch(native,return_value=SimpleNamespace(sender_id='demo-sender-b')):
            self.assertEqual((await self.tools.retrieve_card_policy('Replace card')).llm_response,{'status':'needs_demo_code'})
            await self.tools.select_policy_demo('222222')
            self.assertEqual((await self.tools.retrieve_card_policy('Replace card')).llm_response['sources'][0]['id'],'B-201')
        with patch(native,return_value=SimpleNamespace(sender_id='demo-sender-a')):
            self.assertEqual((await self.tools.retrieve_card_policy('Replace card')).llm_response['sources'][0]['id'],'P-101')

    async def test_native_rebinding_is_refused(self):
        with patch.object(self.tools,'session',return_value=PolicySession()):
            await self.tools.select_policy_demo('111111')
            self.assertEqual((await self.tools.select_policy_demo('222222')).llm_response,{'status':'demo_identity_changed'})
            self.assertEqual((await self.tools.retrieve_card_policy('Replace card')).llm_response['sources'][0]['id'],'P-101')

if __name__ == '__main__':unittest.main()
