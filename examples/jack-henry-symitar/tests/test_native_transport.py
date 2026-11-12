"""Use the actual local HTTP/MCP stack with only the vendor boundary replaced."""
import asyncio
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from types import SimpleNamespace

from fixture_control import INSTANCE
from journal import Journal
from local_transport import HostClient
from mock_server import FIXTURE
from native_host import Gateway
from server import local_server
from test_native_host import Client


class NativeTransportTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.journal=Journal(Path(self.temp.name).resolve()/'journal',INSTANCE,initialize=True)
        self.addCleanup(self.journal.close);self.vendor=Client()
        self.gateway=Gateway(self.vendor,self.journal,json.loads(FIXTURE.read_text()))
        self.server=local_server(None,'x'*40,gateway=self.gateway)
        self.thread=threading.Thread(target=self.server.serve_forever,kwargs={'poll_interval':.01});self.thread.start()
        self.addCleanup(self.server.server_close);self.addCleanup(self.thread.join);self.addCleanup(self.server.shutdown)
        self.url='http://127.0.0.1:'+str(self.server.server_port)
        self.client=HostClient(self.url,'x'*40)
        self.token=(await asyncio.to_thread(self.client.control,'open',sender='real-channel'))['credential']
        await asyncio.to_thread(self.client.control,'turn',credential=self.token,number=1,text='review',revoked=False,cancelled=False)

    async def test_real_mcp_review_does_not_send_private_delivery_next_input_does(self):
        review=await self.client.call(self.token,'banking_review_transfer',{'source':'checking','destination':'savings','amount':'1.25'})
        self.assertEqual(review['state'],'review_pending_delivery');self.assertEqual(self.vendor.sends,[])
        private=await asyncio.to_thread(self.client.control,'review',credential=self.token)
        await asyncio.to_thread(self.client.control,'delivered',credential=self.token,review=private['review'])
        result=await asyncio.to_thread(self.client.control,'turn',credential=self.token,number=2,text='yes',revoked=False,cancelled=False)
        self.assertEqual(result['state'],'accepted');self.assertEqual(len(self.vendor.sends),1)
        self.assertEqual((await self.client.call(self.token,'banking_transfer_status',{}))['state'],'accepted')

    async def test_master_capability_is_not_a_model_session_and_control_is_not_a_tool(self):
        with self.assertRaises(Exception):await self.client.call('x'*40,'banking_accounts',{})
        with self.assertRaises(Exception):await self.client.call(self.token,'confirm',{})
        with self.assertRaises(Exception):await self.client.call(self.token,'banking_review_transfer',{'source':'checking','destination':'savings','amount':1.25})
        self.assertEqual(self.vendor.sends,[])

    async def test_native_binding_delivers_canonical_review_and_returns_actual_tool_result(self):
        import native_adapter
        from rasa.mantle.hooks.payloads import IncomingMessagePayload
        class Context:
            is_cancelled=False
            def __init__(self):self.messages=[]
            async def send(self,text):self.messages.append(text)
        context=Context();native_adapter._conversations.clear()
        with patch.dict('os.environ',{'SYMITAR_HOST_URL':self.url,'SYMITAR_HOST_CAPABILITY':'x'*40}), patch.object(native_adapter,'current_turn_context',return_value=SimpleNamespace(sender_id='native-channel')):
            await native_adapter.incoming(IncomingMessagePayload(sender_id='native-channel',text='balance',message_id='n1'))
            result=await native_adapter.banking_balance('checking',context=context)
            self.assertEqual(result.llm_response['amount'],'1200.50')
            review=await native_adapter.banking_review_transfer('checking','savings','1.25',context=context)
            self.assertEqual(review.llm_response['state'],'review_delivered')
            self.assertIn('USD 1.25 from checking to savings',context.messages[-1])
            self.assertFalse(any(name=='postTransfer' for name,_ in self.vendor.sends))
            await native_adapter.incoming(IncomingMessagePayload(sender_id='native-channel',text='yes',message_id='n2'))
            result=await native_adapter.banking_transfer_status(context=context)
            self.assertEqual(result.llm_response['state'],'accepted')
            self.assertEqual(sum(name=='postTransfer' for name,_ in self.vendor.sends),1)
            self.assertIn('not a real payment',context.messages[-1])

    async def test_inspector_runtime_layout_preserves_selected_voice_and_public_url(self):
        from rasa.core.config.channel_loading import resolve_channels_config
        from launcher import prepare_runtime
        with tempfile.TemporaryDirectory() as temporary:
            run=Path(temporary)
            prepare_runtime(run,'https://fictional-5005.app.github.dev')
            credentials=resolve_channels_config(project_root=run)
            self.assertIsNotNone(credentials)
            inspector=credentials.channels['inspector']
            self.assertEqual(inspector['server_url'],'https://fictional-5005.app.github.dev')
            self.assertEqual(inspector['asr']['name'],'voice_privacy.OptOutASR')
            self.assertEqual(inspector['tts']['name'],'voice_privacy.OptOutTTS')

    async def test_sdk_validates_real_project_and_seven_tools_plus_incoming_modifier(self):
        from rasa.mantle.validation import validate_project
        await asyncio.to_thread(validate_project,Path(__file__).resolve().parent.parent)

    async def test_actual_hook_processes_raw_turn_without_model_and_deduplicates_message_id(self):
        import native_adapter
        from rasa.mantle.hooks.payloads import IncomingMessagePayload
        native_adapter._conversations.clear()
        with patch.dict('os.environ',{'SYMITAR_HOST_URL':self.url,'SYMITAR_HOST_CAPABILITY':'x'*40}):
            payload=IncomingMessagePayload(sender_id='hook-channel',text='review',message_id='first')
            self.assertIs(await native_adapter.incoming(payload),payload)
            conv=native_adapter._conversations[(self.url,'hook-channel')]
            await self.client.call(conv.credential,'banking_review_transfer',{'source':'checking','destination':'savings','amount':'1.25'})
            review=await asyncio.to_thread(self.client.control,'review',credential=conv.credential)
            await asyncio.to_thread(self.client.control,'delivered',credential=conv.credential,review=review['review'])
            yes=IncomingMessagePayload(sender_id='hook-channel',text='yes',message_id='second')
            await native_adapter.incoming(yes);await native_adapter.incoming(yes)
            self.assertEqual(conv.observed,2);self.assertEqual(len(self.vendor.sends),1)
            self.assertEqual(conv.outcome['state'],'accepted')
