import unittest
from rasa_room.room_fixture import observe_late_text

class NativeRoomInput(unittest.IsolatedAsyncioTestCase):
    async def test_native_pre_read_participant_check_cannot_own_late_completion(self):
        plain=await observe_late_text(guarded=False);guarded=await observe_late_text()
        self.assertEqual(plain["native_linked_participant"],"public-b")
        self.assertEqual(guarded["native_linked_participant"],"public-b")
        self.assertEqual(plain["session_replies_after_handoff"],["Synthetic old text."])
        self.assertEqual(guarded["session_replies_after_handoff"],[])
        self.assertEqual(guarded["discarded"],1)

    async def test_same_identity_reconnect_needs_connection_ownership(self):
        plain=await observe_late_text(guarded=False,reconnect=True);guarded=await observe_late_text(reconnect=True)
        self.assertEqual(plain["native_linked_participant"],"public-a")
        self.assertEqual(guarded["native_linked_participant"],"public-a")
        self.assertEqual(plain["session_replies_after_handoff"],["Synthetic old text."])
        self.assertEqual(guarded["session_replies_after_handoff"],[])

    async def test_current_connection_reaches_session_with_native_text_event(self):
        import asyncio
        from livekit.agents.voice.room_io import RoomIO,RoomOptions
        from rasa_room.room_fixture import RoomBoundary,SessionBoundary,ReaderBoundary,participant
        from rasa_room.text_input import BoundTextInput
        from rasa_room.binding import Conversation
        room=RoomBoundary();p=participant('public-a','current');room.remote_participants[p.identity]=p
        session=SessionBoundary();io=RoomIO(session,room,participant=p.identity,options=RoomOptions(close_on_disconnect=False));guard=BoundTextInput(room,Conversation(room.name,p.identity));io.register_text_input(guard);io.set_participant(p.identity)
        reader=ReaderBoundary();io._on_chat_text_stream(reader,p.identity);await asyncio.wait_for(reader.started.wait(),2);reader.pending.set_result('Current question.');await asyncio.gather(*tuple(io._tasks))
        self.assertEqual(session.replies,['Current question.']);self.assertEqual(guard.discarded,0);self.assertEqual(session.interrupts,1)

    async def test_native_room_filter_ignores_other_participant_before_reading(self):
        from livekit.agents.voice.room_io import RoomIO,RoomOptions
        from rasa_room.room_fixture import RoomBoundary,SessionBoundary,ReaderBoundary,participant
        room=RoomBoundary();a=participant('public-a','a');b=participant('public-b','b');room.remote_participants={a.identity:a,b.identity:b};session=SessionBoundary();io=RoomIO(session,room,participant=a.identity,options=RoomOptions(close_on_disconnect=False));io.register_text_input(lambda session,event:None);io.set_participant(a.identity)
        reader=ReaderBoundary();io._on_chat_text_stream(reader,b.identity)
        self.assertFalse(reader.started.is_set());self.assertEqual(io._tasks,set());self.assertEqual(session.replies,[])

    async def test_connection_is_checked_again_after_awaited_session_interrupt(self):
        import asyncio
        from livekit.agents.voice.room_io import RoomIO,RoomOptions
        from rasa_room.room_fixture import RoomBoundary,SessionBoundary,ReaderBoundary,participant
        from rasa_room.text_input import BoundTextInput
        from rasa_room.binding import Conversation
        room=RoomBoundary();a=participant('public-a','a');room.remote_participants[a.identity]=a
        class SwitchingSession(SessionBoundary):
            async def interrupt(self):room.remote_participants[a.identity]=participant('public-a','replacement')
        session=SwitchingSession();io=RoomIO(session,room,participant=a.identity,options=RoomOptions(close_on_disconnect=False));guard=BoundTextInput(room,Conversation(room.name,a.identity));io.register_text_input(guard);io.set_participant(a.identity)
        reader=ReaderBoundary();io._on_chat_text_stream(reader,a.identity);await asyncio.wait_for(reader.started.wait(),2);reader.pending.set_result('Old connection.');await asyncio.gather(*tuple(io._tasks));self.assertEqual(session.replies,[]);self.assertEqual(guard.discarded,1)
