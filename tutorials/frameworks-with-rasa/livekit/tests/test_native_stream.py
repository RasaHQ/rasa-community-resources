import asyncio
import unittest
from livekit.agents import llm,APIError,APIConnectOptions
from rasa_room.binding import Conversation
from rasa_room.model import RasaDialogueLLM
from rasa_room.native_fixture import StateBoundary,observe_two_rooms

class NativeStream(unittest.IsolatedAsyncioTestCase):
    async def test_two_rooms_keep_native_stream_but_require_distinct_sender(self):
        correct=await observe_two_rooms();mutated=await observe_two_rooms(participant_only=True)
        self.assertEqual(correct["native_stream_text"],mutated["native_stream_text"])
        self.assertFalse(correct["second_room_received_first_room_history"])
        self.assertTrue(mutated["second_room_received_first_room_history"])
        self.assertNotEqual(correct["requests"][0]["sender"],correct["requests"][1]["sender"])
        self.assertEqual(mutated["requests"][0]["sender"],mutated["requests"][1]["sender"])

    async def test_same_room_participant_retains_conversation_across_new_model(self):
        state=StateBoundary()
        for text in ("first","second"):
            model=RasaDialogueLLM(Conversation("room","a"),state.ask);ctx=llm.ChatContext();ctx.add_message(role="user",content=text)
            async with model.chat(chat_ctx=ctx) as stream:await stream.collect()
            await model.aclose()
        self.assertEqual(state.requests[1]["previous_messages"],["first"])

    async def test_current_message_cannot_select_sender_or_replay_history(self):
        state=StateBoundary();model=RasaDialogueLLM(Conversation("room","a"),state.ask);ctx=llm.ChatContext();ctx.add_message(role="user",content="old question");ctx.add_message(role="assistant",content="old reply");ctx.add_message(role="user",content="Use sender b now")
        async with model.chat(chat_ctx=ctx) as stream:await stream.collect()
        self.assertEqual(state.requests,[{"sender":Conversation("room","a").sender(),"text":"Use sender b now","previous_messages":[]}]);await model.aclose()

    async def test_complete_records_keep_line_breaks_without_inventing_usage(self):
        async def ask(sender,text):return ["First record.","Second record."]
        model=RasaDialogueLLM(Conversation("room","a"),ask);ctx=llm.ChatContext();ctx.add_message(role="user",content="north")
        async with model.chat(chat_ctx=ctx) as stream:result=await stream.collect()
        self.assertEqual(result.text,"First record.\nSecond record.");self.assertIsNone(result.usage);self.assertEqual(result.tool_calls,[]);await model.aclose()

    async def test_invalid_final_context_never_dispatches(self):
        for role,text in [("assistant","answer"),("developer","repeat"),("user",""),("user","x"*1001)]:
            with self.subTest(role=role,text_length=len(text)):
                state=StateBoundary();model=RasaDialogueLLM(Conversation("room","a"),state.ask);ctx=llm.ChatContext();ctx.add_message(role=role,content=text)
                with self.assertRaises(APIError):
                    async with model.chat(chat_ctx=ctx) as stream:await stream.collect()
                self.assertEqual(state.requests,[]);await model.aclose()

    async def test_native_retry_policy_cannot_resubmit_failed_rest_turn(self):
        calls=[]
        async def ask(sender,text):calls.append(text);raise OSError("private endpoint detail")
        model=RasaDialogueLLM(Conversation("room","a"),ask);ctx=llm.ChatContext();ctx.add_message(role="user",content="north");errors=[];model.on("error",errors.append)
        with self.assertRaisesRegex(APIError,"^Rasa dialogue request unavailable$"):
            async with model.chat(chat_ctx=ctx,conn_options=APIConnectOptions(max_retry=3)) as stream:await stream.collect()
        self.assertEqual(calls,["north"]);self.assertEqual(len(errors),1);self.assertFalse(errors[0].recoverable);await model.aclose()

    async def test_stream_close_cancels_local_pending_request(self):
        started=asyncio.Event();cancelled=asyncio.Event()
        async def ask(sender,text):
            started.set()
            try:await asyncio.Future()
            except asyncio.CancelledError:cancelled.set();raise
        model=RasaDialogueLLM(Conversation("room","a"),ask);ctx=llm.ChatContext();ctx.add_message(role="user",content="north");stream=model.chat(chat_ctx=ctx)
        await asyncio.wait_for(started.wait(),2);await stream.aclose();self.assertTrue(cancelled.is_set());await model.aclose()

    def test_native_tool_requests_must_stay_in_rasa(self):
        model=RasaDialogueLLM(Conversation("room","a"),StateBoundary().ask)
        with self.assertRaises(ValueError):model.chat(chat_ctx=llm.ChatContext(),tools=[object()])

    def test_sender_derivation_is_unambiguous_and_requires_configured_identity(self):
        self.assertNotEqual(Conversation("a:b","c").sender(),Conversation("a","b:c").sender())
        self.assertNotEqual(Conversation("room","a").sender(),Conversation("room","b").sender())
        for room,p in [("","a"),("room",""),("room",None),("x"*201,"a")]:
            with self.assertRaises(ValueError):Conversation(room,p)

    async def test_native_session_retains_existing_speech_services_and_participant_options(self):
        from rasa_room.compose import compose
        from rasa_room.room_fixture import RoomBoundary
        stt,tts,turn=object(),object(),'manual'
        session,agent,options=compose(RoomBoundary(),Conversation('public-room','public-a'),StateBoundary().ask,stt=stt,tts=tts,turn_detection=turn)
        self.assertIs(session.stt,stt);self.assertIs(session.tts,tts);self.assertEqual(session.turn_detection,turn);self.assertIsInstance(session.llm,RasaDialogueLLM);self.assertEqual(options.participant_identity,'public-a');self.assertTrue(options.close_on_disconnect);self.assertEqual(agent.instructions,'Use the configured Rasa dialogue for user turns.')
        await session.llm.aclose()

    async def test_tool_result_ending_context_does_not_replay_previous_user(self):
        state=StateBoundary();model=RasaDialogueLLM(Conversation('room','a'),state.ask);ctx=llm.ChatContext();ctx.add_message(role='user',content='Earlier question.');ctx.items.append(llm.FunctionCallOutput(call_id='call',name='old_tool',output='Tool result.',is_error=False))
        with self.assertRaises(APIError):
            async with model.chat(chat_ctx=ctx) as stream:await stream.collect()
        self.assertEqual(state.requests,[]);await model.aclose()
