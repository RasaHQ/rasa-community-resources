"""Complete text only for the same configured participant connection."""
from .binding import Conversation

class BoundTextInput:
    def __init__(self,room,conversation:Conversation):
        self.room,self.conversation=room,conversation
        self.discarded=0

    def owns(self,event):
        participant=event.participant
        return (
            self.room.name==self.conversation.room
            and participant is not None
            and participant.identity==self.conversation.participant
            and self.room.remote_participants.get(participant.identity) is participant
        )

    async def __call__(self,session,event):
        if not self.owns(event): self.discarded+=1;return
        if not event.text.strip() or len(event.text)>1000: self.discarded+=1;return
        await session.interrupt()
        if not self.owns(event): self.discarded+=1;return
        session.generate_reply(user_input=event.text)
