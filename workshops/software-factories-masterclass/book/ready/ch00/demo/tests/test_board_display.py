"""Display transport refuses public hosts and capability-bearing URLs."""
import unittest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from briefing.board_display import BoardDisplay


class BoardDisplayTests(unittest.IsolatedAsyncioTestCase):
    async def request(self, *, host=b'127.0.0.1:8942', client='127.0.0.1', origin=None,
                      query=b'', method='GET', fail=False, path='/cards'):
        self.render_calls = 0
        async def other(scope, receive, send):
            raise AssertionError('Cards must not reach the authenticated MCP app')
        def render():
            self.render_calls += 1
            if fail:
                raise ValueError('brf_canary-private-capability')
            return '<p>REPLAY</p>'
        app = BoardDisplay(other, render_current=render)
        messages = []
        async def send(message):
            messages.append(message)
        headers = [(b'host', host)]
        if origin is not None:
            headers.append((b'origin', origin))
        await app({'type':'http', 'path':path, 'method':method, 'headers':headers,
                   'client':(client, 1), 'query_string':query}, None, send)
        return messages

    async def test_local_page_refreshes_without_scripts_or_external_assets(self):
        start, body = await self.request()
        self.assertEqual(start['status'], 200)
        headers = dict(start['headers'])
        self.assertEqual(headers[b'refresh'], b'2')
        self.assertEqual(headers[b'cache-control'], b'no-store')
        self.assertIn(b"default-src 'none'", headers[b'content-security-policy'])
        self.assertEqual(body['body'], b'<p>REPLAY</p>')

    async def test_combined_page_keeps_conversation_stable_and_loads_only_local_frames(self):
        start, body = await self.request(path='/')
        self.assertEqual(start['status'], 200)
        self.assertNotIn(b'refresh', dict(start['headers']))
        self.assertIn(b'frame-src', dict(start['headers'])[b'content-security-policy'])
        self.assertIn(b'http://127.0.0.1:5005/webhooks/inspector/inspect.html', body['body'])
        self.assertIn(b'src="/cards"', body['body'])
        self.assertNotIn(b'<script', body['body'])
        self.assertEqual(self.render_calls, 0)
        start, body = await self.request(path='/', query=b'briefing_id=brf_canary')
        self.assertEqual(start['status'], 400)
        self.assertNotIn(b'brf_canary', body['body'])

    async def test_remote_host_origin_client_and_capability_url_never_render(self):
        for args in ({'host':b'hostile.example'}, {'client':'192.0.2.1'},
                     {'origin':b'https://hostile.example'}, {'query':b'briefing_id=brf_canary'},
                     {'method':'POST'}):
            with self.subTest(args=args):
                start, body = await self.request(**args)
                self.assertIn(start['status'], (400, 403))
                self.assertEqual(self.render_calls, 0)
                self.assertNotIn(b'brf_canary', body['body'])

    async def test_renderer_error_is_value_free_unavailable(self):
        start, body = await self.request(fail=True)
        self.assertEqual(start['status'], 503)
        self.assertEqual(body['body'], b'Briefing board unavailable')
        self.assertNotIn(b'brf_', body['body'])
