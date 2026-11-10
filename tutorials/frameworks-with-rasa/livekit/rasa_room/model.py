"""Use the native LiveKit LLM interface for an external Rasa dialogue."""
from collections.abc import Awaitable, Callable
from dataclasses import replace
from uuid import uuid4
from livekit.agents import llm, APIError, APIConnectOptions, DEFAULT_API_CONNECT_OPTIONS
from .binding import Conversation

class RasaDialogueLLM(llm.LLM):
    def __init__(self, conversation: Conversation, ask: Callable[[str,str],Awaitable[list[str]]]):
        super().__init__()
        self.conversation,self.ask=conversation,ask

    @property
    def model(self): return "rasa-rest-buffered"

    @property
    def provider(self): return "configured-rasa-endpoint"

    def chat(self, *, chat_ctx, tools=None, conn_options=DEFAULT_API_CONNECT_OPTIONS, **kwargs):
        # A REST turn can have changed server state before a connection fails.
        # Do not let generic LLM retries submit the same turn a second time.
        options=replace(conn_options,max_retry=0)
        if tools: raise ValueError("Keep dialogue tools in the configured Rasa project")
        return RasaStream(self,chat_ctx=chat_ctx,tools=[],conn_options=options)

class RasaStream(llm.LLMStream):
    async def _run(self):
        last=self.chat_ctx.items[-1] if self.chat_ctx.items else None
        if not isinstance(last,llm.ChatMessage) or last.role!="user" or len(last.content)!=1 or not isinstance(last.content[0],str):
            raise APIError("Rasa dialogue requires a final plain-text user message",retryable=False)
        question=last.content[0]
        if not question.strip() or len(question)>1000:
            raise APIError("Rasa dialogue requires usable user text",retryable=False)
        try:
            replies=await self._llm.ask(self._llm.conversation.sender(),question)
        except Exception:
            raise APIError("Rasa dialogue request unavailable",retryable=False) from None
        if replies:
            self._event_ch.send_nowait(llm.ChatChunk(id="rasa-"+uuid4().hex,delta=llm.ChoiceDelta(role="assistant",content="\n".join(replies))))
