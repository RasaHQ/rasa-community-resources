"""Retain LiveKit speech components and select one public participant."""
from livekit.agents import Agent,AgentSession
from livekit.agents.voice.room_io import RoomOptions,TextInputOptions
from .model import RasaDialogueLLM
from .text_input import BoundTextInput

def compose(room,conversation,ask,*,stt,tts,turn_detection):
    model=RasaDialogueLLM(conversation,ask)
    session=AgentSession(stt=stt,tts=tts,turn_detection=turn_detection,llm=model)
    options=RoomOptions(participant_identity=conversation.participant,text_input=TextInputOptions(text_input_cb=BoundTextInput(room,conversation)))
    # Domain instructions and tools live in the configured Rasa project.
    agent=Agent(instructions="Use the configured Rasa dialogue for user turns.")
    return session,agent,options
