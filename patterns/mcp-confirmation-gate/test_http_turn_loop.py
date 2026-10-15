"""Real loopback HTTP through Rasa's REST channel; only the model is scripted.

This adds HTTP routing/serialization to the archived turn-loop control. It
does not run the `rasa run` CLI, use a real model, or test voice consent.
"""
import unittest
from uuid import uuid4

import httpx
from sanic import Sanic
from rasa.core.channels.rest import RestInput

import test_turn_loop as turns


class PairedHttpTurnLoop(turns.PairedTurnLoop):
    async def send_message(self, agent, text, output, sender):
        if not getattr(self, 'server', None):
            self.app = Sanic(f'mcp-gate-{uuid4().hex}')
            # Rasa wraps Sanic's send method; Sanic's source-rewriting
            # optimisation cannot transform that wrapper in this in-process
            # harness. Disable only the optimisation, retaining the real route.
            self.app.config.TOUCHUP = False
            self.app.ctx.agent = agent
            self.app.blueprint(RestInput().blueprint(agent.handle_message),
                url_prefix='/webhooks/rest')
            self.server = await self.app.create_server(host='127.0.0.1', port=0,
                return_asyncio_server=True, access_log=False)
            await self.server.startup()
            await self.server.start_serving()
            port = self.server.server.sockets[0].getsockname()[1]
            self.client = httpx.AsyncClient(base_url=f'http://127.0.0.1:{port}',
                trust_env=False, timeout=30)
            health = await self.client.get('/webhooks/rest/')
            self.assertEqual(health.status_code, 200)
            self.assertEqual(health.json(), {'status': 'ok'})
        response = await self.client.post('/webhooks/rest/webhook',
            json={'sender': sender, 'message': text})
        self.assertEqual(response.status_code, 200)
        messages = response.json()
        self.assertIsInstance(messages, list)
        self.assertTrue(messages, 'REST must return a response, not only mutate a tracker')
        self.assertTrue(all(item.get('recipient_id') == sender for item in messages))
        output.messages.extend(messages)

    async def close_transport(self):
        if getattr(self, 'client', None):
            await self.client.aclose()
            self.client = None
        if getattr(self, 'server', None):
            await self.server.close()
            Sanic.unregister_app(self.app)
            self.server = None


if __name__ == '__main__':
    unittest.main()
