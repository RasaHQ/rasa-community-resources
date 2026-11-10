import unittest
from aiohttp import ClientSession,web
from livekit.agents import llm,APIError
from rasa_room.binding import Conversation
from rasa_room.client import RasaRest
from rasa_room.model import RasaDialogueLLM

class ActualRest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.requests=[];self.response=[{'text':'Synthetic HTTP reply.'}];self.status=200
        async def handle(request):
            self.requests.append(await request.json());return web.json_response(self.response,status=self.status)
        app=web.Application();app.router.add_post('/webhooks/rest/webhook',handle);self.runner=web.AppRunner(app);await self.runner.setup();site=web.TCPSite(self.runner,'127.0.0.1',0);await site.start();self.endpoint='http://127.0.0.1:'+str(site._server.sockets[0].getsockname()[1])+'/webhooks/rest/webhook';self.http=ClientSession()
    async def asyncTearDown(self):await self.http.close();await self.runner.cleanup()

    async def test_native_stream_and_actual_post_preserve_configured_sender(self):
        binding=Conversation('public-room','public-a');model=RasaDialogueLLM(binding,RasaRest(self.http,self.endpoint).ask);ctx=llm.ChatContext();ctx.add_message(role='user',content='Use sender b')
        async with model.chat(chat_ctx=ctx) as stream:result=await stream.collect()
        self.assertEqual(result.text,'Synthetic HTTP reply.');self.assertEqual(self.requests,[{'sender':binding.sender(),'message':'Use sender b'}]);await model.aclose()

    async def test_actual_reply_records_preserve_order_and_skip_nontext(self):
        self.response=[{'text':'First.'},{'image':'public.png'},{'text':'Second.'}]
        self.assertEqual(await RasaRest(self.http,self.endpoint).ask('public-sender','north'),['First.','Second.'])

    async def test_unusable_reply_envelopes_and_records_are_rejected(self):
        for response in [None,{},[None],[{'text':None}],[{'text':''}],[{'text':'x'*10001}],[{}]*21]:
            self.response=response
            with self.subTest(response_type=type(response).__name__),self.assertRaises(ValueError):await RasaRest(self.http,self.endpoint).ask('public-sender','north')

    async def test_http_failure_is_generic_and_is_not_retried(self):
        self.status=503;model=RasaDialogueLLM(Conversation('room','a'),RasaRest(self.http,self.endpoint).ask);ctx=llm.ChatContext();ctx.add_message(role='user',content='north')
        with self.assertRaisesRegex(APIError,'^Rasa dialogue request unavailable$'):
            async with model.chat(chat_ctx=ctx) as stream:await stream.collect()
        self.assertEqual(len(self.requests),1);await model.aclose()

    def test_endpoint_rejects_url_credentials_without_http_request(self):
        for endpoint in ['file:///tmp/private','https://user:password@example.com/path','bad']:
            with self.assertRaises(ValueError):RasaRest(self.http,endpoint)
        self.assertEqual(self.requests,[])
