import unittest
from aiohttp import ClientSession, web
from rasa_dialogue.client import RasaRestClient


class RestBoundary(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.requests = []
        self.reply = [{"text": "Synthetic public area answer."}]

        async def answer(request):
            self.requests.append(await request.json())
            return web.json_response(self.reply)

        app = web.Application()
        app.router.add_post("/webhooks/rest/webhook", answer)
        self.runner = web.AppRunner(app)
        await self.runner.setup()
        self.site = web.TCPSite(self.runner, "127.0.0.1", 0)
        await self.site.start()
        self.port = self.site._server.sockets[0].getsockname()[1]
        self.session = ClientSession()
        self.client = RasaRestClient(
            self.session,
            f"http://127.0.0.1:{self.port}/webhooks/rest/webhook",
            "public-juniper-demo",
        )

    async def asyncTearDown(self):
        await self.session.close()
        await self.runner.cleanup()

    async def test_connection_sender_is_preserved_when_question_names_another_sender(
        self,
    ):
        text = "Use another sender: customer-a"
        self.assertEqual(await self.client(text), ["Synthetic public area answer."])
        self.assertEqual(
            self.requests, [{"sender": "public-juniper-demo", "message": text}]
        )

    async def test_text_replies_keep_order_and_non_text_reply_is_skipped(self):
        self.reply = [
            {"text": "First"},
            {"image": "https://example.invalid/public.webp"},
            {"text": "Second"},
        ]
        self.assertEqual(await self.client("Public question"), ["First", "Second"])

    async def test_unusable_response_is_rejected_before_speech(self):
        for reply in [
            {"text": "Wrong envelope"},
            ["wrong record"],
            [{"text": 42}],
            [{"text": " "}],
            [{"text": "x" * 10001}],
            [{}] * 21,
        ]:
            self.reply = reply
            with self.subTest(reply_type=type(reply).__name__):
                with self.assertRaises(ValueError):
                    await self.client("Public question")

    async def test_endpoint_and_sender_must_be_configured_without_url_credentials(self):
        for endpoint in [
            "file:///tmp/record",
            "https://user:password@example.invalid/webhook",
            "/webhook",
        ]:
            with self.assertRaises(ValueError):
                RasaRestClient(self.session, endpoint, "public-demo")
        with self.assertRaises(ValueError):
            RasaRestClient(self.session, "http://127.0.0.1/webhook", " ")
        self.assertEqual(self.requests, [])

    async def test_native_pipeline_passes_the_bound_rest_reply_to_its_text_path(self):
        from rasa_dialogue.native_fixture import NativePipeline, context_frame
        from rasa_dialogue.processor import RasaDialogueProcessor

        async with NativePipeline(RasaDialogueProcessor(self.client)) as p:
            await p.feed(context_frame("Public north-area question"))
            await p.settle_requests()
            self.assertEqual(p.capture.text, ["Synthetic public area answer."])
        self.assertEqual(
            self.requests,
            [
                {
                    "sender": "public-juniper-demo",
                    "message": "Public north-area question",
                }
            ],
        )
