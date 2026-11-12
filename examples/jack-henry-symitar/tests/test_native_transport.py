"""Use the actual local HTTP/MCP stack with only the vendor boundary replaced."""
import asyncio
import json
from pathlib import Path
import tempfile
import threading
import time
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
        from lib import native_adapter
        from rasa.mantle.hooks.payloads import IncomingMessagePayload
        class Context:
            is_cancelled=False
            def __init__(self):self.messages=[];self.events=[]
            async def send(self,text):self.messages.append(text)
        context=Context();native_adapter._conversations.clear()
        native=SimpleNamespace(sender_id='native-channel',turn=SimpleNamespace(text='balance'))
        context.events=[SimpleNamespace(as_dict=lambda:{'event':'user','text':'balance','timestamp':time.time()})]
        with patch.dict('os.environ',{'SYMITAR_HOST_URL':self.url,'SYMITAR_HOST_CAPABILITY':'x'*40}), patch.object(native_adapter,'current_turn_context',return_value=native):
            result=await native_adapter.banking_balance('checking',context=context)
            self.assertEqual(result.llm_response['amount'],'1200.50')
            review=await native_adapter.banking_review_transfer('checking','savings','1.25',context=context)
            self.assertEqual(review.llm_response['state'],'review_delivered')
            self.assertIn('USD 1.25 from checking to savings',context.messages[-1])
            self.assertFalse(any(name=='postTransfer' for name,_ in self.vendor.sends))
            native.turn.text='yes'
            context.events.append(SimpleNamespace(as_dict=lambda:{'event':'user','text':'yes','timestamp':time.time()}))
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
            self.assertNotIn('rest',credentials.channels)
            inspector=credentials.channels['inspector']
            self.assertEqual(inspector['server_url'],'https://fictional-5005.app.github.dev')
            self.assertEqual(inspector['asr']['name'],'voice_privacy.OptOutASR')
            self.assertEqual(inspector['tts']['name'],'voice_privacy.OptOutTTS')

    async def test_single_word_confirmation_and_revocation_survive_active_response(self):
        # A drained audio queue does not imply that SDK response processing ended.
        # Exercise its actual handler with no NLI model, without speech/network calls.
        from rasa.core.config.channel_loading import resolve_channels_config
        from rasa.core.channels.voice_stream.call_state import CallState, InterruptionConfig, _call_state
        from rasa.core.voice.event_composition.handlers.barge_in.barge_in_handler import BargeInHandler
        from rasa.core.voice.event_composition.handlers.barge_in import backchannel
        from rasa.core.voice.event_composition.events.input_events import FinalTranscriptInputEvent
        from rasa.core.voice.event_composition.events import BargeInInteractionEvent
        from launcher import prepare_runtime
        with tempfile.TemporaryDirectory() as temporary:
            run=Path(temporary);prepare_runtime(run,'https://fictional-5005.app.github.dev')
            inspector=resolve_channels_config(project_root=run).channels['inspector']
            for text in ('yes','no','cancel'):
                with self.subTest(text=text):
                    state=CallState(is_rasa_processing=True,is_bot_audio_active=False,
                        interruption_config=InterruptionConfig(**inspector.get('interruptions',{'enabled':True})))
                    token=_call_state.set(state)
                    try:
                        queue=SimpleNamespace(conversation_id='fictional-short-input',put=unittest.mock.AsyncMock())
                        with patch.object(backchannel,'loaded_model',return_value=None):
                            handler=BargeInHandler(queue,bot_text_provider=lambda:None)
                            await handler.handle(FinalTranscriptInputEvent(text=text))
                        self.assertTrue(state.barge_in_accepted)
                        self.assertIsInstance(queue.put.call_args.args[0],BargeInInteractionEvent)
                    finally:
                        _call_state.reset(token)

    async def test_old_yes_after_prior_success_reports_current_review_not_submitted(self):
        from lib import native_adapter
        native_adapter._conversations.clear()
        events=[{'event':'user','text':'review','timestamp':time.time()}]
        class Context:
            is_cancelled=False
            def __init__(self):self.messages=[]
            @property
            def events(self):return [SimpleNamespace(as_dict=lambda event=event:event) for event in events]
            async def send(self,text):self.messages.append(text)
        context=Context();native=SimpleNamespace(sender_id='prior-success-replay',turn=SimpleNamespace(text='review'))
        with patch.dict('os.environ',{'SYMITAR_HOST_URL':self.url,'SYMITAR_HOST_CAPABILITY':'x'*40}),patch.object(native_adapter,'current_turn_context',return_value=native):
            await native_adapter.banking_review_transfer('checking','savings','1.25',context=context)
            original_yes={'event':'user','text':'yes','timestamp':time.time()}
            events.append(original_yes);native.turn.text='yes'
            first=await native_adapter.banking_transfer_status(context=context)
            self.assertEqual(first.llm_response['state'],'accepted')
            events.append({'event':'user','text':'another review','timestamp':time.time()});native.turn.text='another review'
            await native_adapter.banking_review_transfer('checking','savings','1.25',context=context)
            offset=len(context.messages)
            events.append(dict(original_yes))
            events.append({'event':'user','text':'current status','timestamp':time.time()});native.turn.text='current status'
            status=await native_adapter.banking_transfer_status(context=context)
            self.assertEqual(status.llm_response['state'],'not_submitted')
            replies=' '.join(context.messages[offset:]).casefold()
            self.assertIn('older confirmation was not used',replies)
            self.assertIn('no new transfer was sent',replies)
            self.assertNotIn('accepted',replies)
            again=await native_adapter.banking_transfer_status(context=context)
            self.assertEqual(again.llm_response['state'],'not_submitted')
            self.assertEqual(sum(name=='postTransfer' for name,_ in self.vendor.sends),1)

    async def test_native_tracker_never_dispatches_a_historical_no_tool_yes(self):
        from lib import native_adapter
        native_adapter._conversations.clear()
        events=[{'event':'user','text':'review','timestamp':time.time()}]
        class Context:
            is_cancelled=False
            @property
            def events(self):return [SimpleNamespace(as_dict=lambda event=event:event) for event in events]
            async def send(self,text):pass
        context=Context();native=SimpleNamespace(sender_id='historical-yes',turn=SimpleNamespace(text='review'))
        with patch.dict('os.environ',{'SYMITAR_HOST_URL':self.url,'SYMITAR_HOST_CAPABILITY':'x'*40}),patch.object(native_adapter,'current_turn_context',return_value=native):
            result=await native_adapter.banking_review_transfer('checking','savings','1.25',context=context)
            self.assertEqual(result.llm_response['state'],'review_delivered')
            events.extend([{'event':'user','text':'yes','timestamp':time.time()},{'event':'user','text':'status','timestamp':time.time()}])
            native.turn.text='status'
            result=await native_adapter.banking_transfer_status(context=context)
            self.assertEqual(result.llm_response['state'],'not_submitted')
        self.assertEqual(self.vendor.sends,[])

    async def test_native_tracker_keeps_no_tool_verify_age_and_refuses_stale_grant(self):
        from lib import native_adapter
        native_adapter._conversations.clear()
        events=[{'event':'user','text':'verify me','timestamp':time.time()-301},{'event':'user','text':'balance','timestamp':time.time()}]
        context=SimpleNamespace(is_cancelled=False,events=[SimpleNamespace(as_dict=lambda event=event:event) for event in events])
        native=SimpleNamespace(sender_id='aged-native-channel',turn=SimpleNamespace(text='balance'))
        with patch.dict('os.environ',{'SYMITAR_HOST_URL':self.url,'SYMITAR_HOST_CAPABILITY':'x'*40}),patch.object(native_adapter,'current_turn_context',return_value=native):
            result=await native_adapter.banking_balance('checking',context=context)
        self.assertEqual(result.llm_response['state'],'unavailable')
        self.assertEqual(self.vendor.sends,[])

    async def test_child_environment_drops_unrelated_secrets_and_python_paths(self):
        from launcher import child_environment
        with patch.dict('os.environ',{'GH_TOKEN':'not-a-credential-test-marker','UNRELATED_SECRET':'test-marker','PYTHONPATH':'/unrelated/source','PATH':'/bin'}):
            selected=child_environment()
            self.assertNotIn('GH_TOKEN',selected)
            self.assertNotIn('UNRELATED_SECRET',selected)
            self.assertNotIn('PYTHONPATH',selected)
            self.assertEqual(selected['PATH'],'/bin')

    async def test_lost_private_reply_recovers_original_outcome_without_second_send(self):
        from lib import native_adapter
        from rasa.mantle.hooks.payloads import IncomingMessagePayload
        native_adapter._conversations.clear()
        with patch.dict('os.environ',{'SYMITAR_HOST_URL':self.url,'SYMITAR_HOST_CAPABILITY':'x'*40}):
            await native_adapter.incoming(IncomingMessagePayload(sender_id='lost-reply',text='review',message_id='lost1'))
            conv=native_adapter._conversations[(self.url,'lost-reply')]
            await self.client.call(conv.credential,'banking_review_transfer',{'source':'checking','destination':'savings','amount':'1.25'})
            review=await asyncio.to_thread(self.client.control,'review',credential=conv.credential)
            await asyncio.to_thread(self.client.control,'delivered',credential=conv.credential,review=review['review'])
            original=conv.client.control
            lost=[False]
            def lose_reply(action,**data):
                result=original(action,**data)
                if action=='turn' and data['number']==2 and not lost[0]:
                    lost[0]=True
                    raise TimeoutError('injected post-effect private reply loss')
                return result
            with patch.object(conv.client,'control',side_effect=lose_reply):
                with self.assertRaises(TimeoutError):
                    await native_adapter.incoming(IncomingMessagePayload(sender_id='lost-reply',text='yes',message_id='lost2'))
                await native_adapter.incoming(IncomingMessagePayload(sender_id='lost-reply',text='check status',message_id='lost3'))
            self.assertEqual(conv.observed,3)
            self.assertEqual(conv.outcome['state'],'accepted')
            self.assertEqual(sum(name=='postTransfer' for name,_ in self.vendor.sends),1)
            self.assertFalse(conv.pending_request)

    async def test_private_pre_delivery_failure_then_no_or_logout_never_dispatches(self):
        from lib import native_adapter
        from rasa.mantle.hooks.payloads import IncomingMessagePayload
        for later in ('no','logout','status'):
            native_adapter._conversations.clear()
            sender='pre-delivery-'+later
            with patch.dict('os.environ',{'SYMITAR_HOST_URL':self.url,'SYMITAR_HOST_CAPABILITY':'x'*40}):
                await native_adapter.incoming(IncomingMessagePayload(sender_id=sender,text='review',message_id=sender+'1'))
                conv=native_adapter._conversations[(self.url,sender)]
                await self.client.call(conv.credential,'banking_review_transfer',{'source':'checking','destination':'savings','amount':'1.25'})
                review=await asyncio.to_thread(self.client.control,'review',credential=conv.credential)
                await asyncio.to_thread(self.client.control,'delivered',credential=conv.credential,review=review['review'])
                original=conv.client.control
                dropped=[False]
                def fail_before_host(action,**data):
                    if action=='turn' and data['number']==2 and not dropped[0]:
                        dropped[0]=True
                        raise ConnectionError('injected before host delivery')
                    return original(action,**data)
                with patch.object(conv.client,'control',side_effect=fail_before_host):
                    with self.assertRaises(ConnectionError):
                        await native_adapter.incoming(IncomingMessagePayload(sender_id=sender,text='yes',message_id=sender+'2'))
                    await native_adapter.incoming(IncomingMessagePayload(sender_id=sender,text=later,message_id=sender+'3'))
                # Delayed original request cannot turn recovery into first send.
                late=await asyncio.to_thread(self.client.control,'turn',credential=conv.credential,number=2,text='yes',revoked=False,cancelled=False)
                self.assertNotEqual(late['state'],'accepted')
                self.assertEqual(self.vendor.sends,[])

    async def test_sdk_validates_real_project_and_seven_native_bindings(self):
        from rasa.mantle.validation import validate_project
        await asyncio.to_thread(validate_project,Path(__file__).resolve().parent.parent)

    async def test_actual_hook_processes_raw_turn_without_model_and_deduplicates_message_id(self):
        from lib import native_adapter
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
