"""Actual installed Telegram transport selection, without provider access."""
import asyncio
import json
import socket
import unittest
from unittest.mock import patch

from pydantic import SecretStr
from shop_demo.telegram_poll import POLL_TYPES, poll_updates


class PollContractTests(unittest.IsolatedAsyncioTestCase):
    async def test_every_wire_poll_overrides_discovery_selection(self):
        import httpx
        from zeo_integrations.telegram.direct import TelegramClient
        seen = []
        def transport(request):
            self.assertTrue(request.url.path.endswith('/getUpdates'))
            payload = json.loads(request.content)
            seen.append(payload)
            self.assertEqual(payload['allowed_updates'], list(POLL_TYPES))
            return httpx.Response(200, json={'ok': True, 'result': []})
        with patch.object(socket.socket, 'connect', side_effect=AssertionError('Real network forbidden')):
            async with TelegramClient(SecretStr('1:' + 'synthetic_' * 3), transport=httpx.MockTransport(transport)) as client:
                for offset in (None, 15):
                    await poll_updates(client, offset=offset, limit=20, timeout=10,
                        allowed_updates=POLL_TYPES)
                for invalid in (('edited_message',), ('message',), ('callback_query', 'message'), ['message', 'callback_query']):
                    with self.assertRaises(ValueError):
                        await poll_updates(client, offset=None, limit=20, timeout=10,
                            allowed_updates=invalid)
        self.assertEqual(len(seen), 2)
        self.assertEqual(seen[1]['offset'], 15)
