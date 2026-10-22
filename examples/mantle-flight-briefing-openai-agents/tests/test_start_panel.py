"""The empty board explains the journey instead of claiming unavailable cards."""
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import httpx
from briefing.jobs import Jobs
from briefing.mcp_app import create_app


class StartPanel(unittest.IsolatedAsyncioTestCase):
    async def test_actual_empty_http_board_has_sources_example_and_plain_status(self):
        async def never(work):
            raise AssertionError('No work before the user sends a journey')
        jobs = Jobs(never, ownership_mode='capability')
        app = create_app(jobs, transport_token='synthetic-start-panel-control-only')
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app),
                                     base_url='http://127.0.0.1:8942') as http:
            page = await http.get('/cards')
            self.assertEqual(page.status_code, 200)
            for text in ('Start your briefing', 'Waiting for a briefing', 'already in the air',
                         'New York', 'tomorrow at 6 pm', 'ECB', 'not live quotes'):
                self.assertIn(text, page.text)
            self.assertNotIn('destination=', page.text)
            self.assertNotIn('no cards yet', page.text.lower())
            self.assertNotIn('synthetic-start-panel-control-only', page.text)
            self.assertNotIn('<script', page.text)
        await jobs.close()
