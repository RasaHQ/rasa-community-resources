"""Explicit tailnet viewer transport, with loopback default and refusal controls."""
import sys
from pathlib import Path
import unittest
from unittest.mock import patch
import httpx
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from briefing.board_display import BoardDisplay
from demo_host import validate_host
import demo_launcher as demo


class TailnetDisplay(unittest.IsolatedAsyncioTestCase):
    async def test_explicit_bind_renders_matching_iframe_and_csp(self):
        for host, peer, browser in [('127.0.0.1', '127.0.0.1', '127.0.0.1'),
                ('100.123.206.49', '100.64.0.2', 'mac-mini.tail29b7b0.ts.net')]:
            app = BoardDisplay(None, render_current=lambda: '<p>Validated cards</p>', host=host)
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app, client=(peer, 1234)),
                                         base_url='http://' + browser + ':8942') as client:
                response = await client.get('/')
                self.assertEqual(response.status_code, 200)
                self.assertIn('http://' + host + ':5005/webhooks/inspector/inspect.html', response.text)
                self.assertIn('http://' + host + ':5005', response.headers['content-security-policy'])
                self.assertEqual((await client.get('/cards')).status_code, 200)
                self.assertEqual((await client.get('/', headers={'Host': 'evil.invalid'})).status_code, 403)
                self.assertEqual((await client.get('/', headers={'Origin': 'http://evil.invalid'})).status_code, 403)

    async def test_tailnet_never_accepts_public_peer_or_loopback_remote_peer(self):
        for host, peer in [('100.123.206.49', '203.0.113.2'), ('127.0.0.1', '100.64.0.2')]:
            app = BoardDisplay(None, render_current=lambda: '', host=host)
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app, client=(peer, 1234)),
                                         base_url='http://' + host + ':8942') as client:
                self.assertEqual((await client.get('/')).status_code, 403)

    def test_launcher_keeps_default_and_accepts_only_assigned_tailnet(self):
        for argv, host in [(['run'], '127.0.0.1'),
                           (['run', '--host', '100.123.206.49'], '100.123.206.49')]:
            with patch.object(demo, 'run_demo') as run:
                self.assertEqual(demo.main(argv), 0)
                run.assert_called_once_with(scripted=False, host=host)
        for host in ['0.0.0.0', '203.0.113.2', 'evil.invalid']:
            with self.assertRaises(ValueError):
                validate_host(host)
