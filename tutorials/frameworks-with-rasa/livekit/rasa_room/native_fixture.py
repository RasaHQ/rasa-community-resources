"""Native LLMStream with an inspectable synthetic server-state boundary."""
from livekit.agents import llm
from .binding import Conversation
from .model import RasaDialogueLLM

class StateBoundary:
    def __init__(self): self.history={}; self.requests=[]
    async def ask(self,sender,text):
        before=list(self.history.get(sender,[])); self.requests.append({"sender":sender,"text":text,"previous_messages":before})
        self.history.setdefault(sender,[]).append(text)
        return ["Synthetic reply."]

async def observe_two_rooms(*,participant_only=False):
    boundary=StateBoundary(); results=[]
    for room,text in [("north-room","Is maintenance planned for north?"),("central-room","And for central?")]:
        binding=Conversation(room,"public-caller")
        if participant_only:
            # Deliberate routing mutation: omit only room from the actual
            # sender derivation; keep native stream and server boundary.
            binding=Conversation("room-omitted","public-caller")
        model=RasaDialogueLLM(binding,boundary.ask)
        context=llm.ChatContext();context.add_message(role="user",content=text)
        async with model.chat(chat_ctx=context) as stream:
            response=await stream.collect(); results.append(response.text)
        await model.aclose()
    return {"room_in_sender":not participant_only,"native_stream_text":results,"requests":boundary.requests,"second_room_received_first_room_history":bool(boundary.requests[1]["previous_messages"])}
