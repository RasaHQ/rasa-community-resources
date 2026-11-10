"""Actual RoomIO with synthetic participant, reader and session boundaries."""
import asyncio
from types import SimpleNamespace
from livekit.agents.voice.room_io import RoomIO,RoomOptions
from livekit import rtc
from .binding import Conversation
from .text_input import BoundTextInput

class SessionBoundary:
    def __init__(self):self.replies=[];self.linked=[];self.interrupts=0
    def _cancel_user_away_timer(self):pass
    def _on_room_io_participant_linked(self,p):self.linked.append(p.identity)
    async def interrupt(self):self.interrupts+=1
    def generate_reply(self,*,user_input):self.replies.append(user_input)

class RoomBoundary:
    def __init__(self,name="public-room"):
        self.name=name;self.remote_participants={};self.handlers={}
        self.local_participant=SimpleNamespace(identity="agent")
    def register_text_stream_handler(self,topic,handler):self.handlers[topic]=handler

class ReaderBoundary:
    def __init__(self):self.pending=asyncio.get_running_loop().create_future();self.started=asyncio.Event();self.info=None
    async def read_all(self):self.started.set();return await self.pending

def participant(identity,sid):
    return SimpleNamespace(identity=identity,sid=sid,kind=rtc.ParticipantKind.PARTICIPANT_KIND_STANDARD,attributes={},name="Synthetic caller",metadata="",disconnect_reason=rtc.DisconnectReason.UNKNOWN_REASON)

async def observe_late_text(*,guarded=True,reconnect=False):
    room=RoomBoundary();old=participant("public-a","old-connection");other=participant("public-a" if reconnect else "public-b","new-connection");room.remote_participants[old.identity]=old
    session=SessionBoundary();io=RoomIO(session,room,participant=old.identity,options=RoomOptions(close_on_disconnect=False))
    guard=BoundTextInput(room,Conversation(room.name,old.identity))
    async def unguarded(sess,event):
        await sess.interrupt();sess.generate_reply(user_input=event.text)
    io.register_text_input(guard if guarded else unguarded)
    io.set_participant(old.identity)
    reader=ReaderBoundary();io._on_chat_text_stream(reader,old.identity);await asyncio.wait_for(reader.started.wait(),2)
    # Exercise actual native disconnect/link handling while read_all is pending.
    io._on_participant_disconnected(old)
    room.remote_participants.pop(old.identity)
    room.remote_participants[other.identity]=other
    io.set_participant(other.identity)
    reader.pending.set_result("Synthetic old text.")
    tasks=tuple(io._tasks)
    if tasks:await asyncio.wait_for(asyncio.gather(*tasks),2)
    return {"guarded":guarded,"reconnect_same_identity":reconnect,"native_linked_participant":io.linked_participant.identity,"session_replies_after_handoff":session.replies,"discarded":guard.discarded}
