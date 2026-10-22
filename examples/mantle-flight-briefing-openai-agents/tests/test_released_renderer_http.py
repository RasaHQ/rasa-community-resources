"""Actual released Core renderer through the class HTTP path; no provider call."""
import asyncio
from importlib.metadata import version
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from briefing.jobs import Jobs, Owner
from briefing.mcp_app import create_app
from briefing.replay import ReplayRunner
import httpx


class ReleasedRendererHTTP(unittest.IsolatedAsyncioTestCase):
    async def test_actual_replay_board_reaches_the_page_without_a_renderer_stub(self):
        self.assertNotIn('.dev', version('zeocore'))
        runner = ReplayRunner()
        jobs = Jobs(runner, replacement_plan=runner.replacement_plan,
                    ownership_mode='capability')
        owner = Owner('mantle', 'capability-possession')
        started = await jobs.briefing(owner, action='start', request='Replay DEMO101')
        try:
            for _ in range(100):
                result = await jobs.briefing(owner, action='get', job_id=started['job_id'])
                if result['status'] not in ('started', 'running'):
                    break
                await asyncio.sleep(.01)
            self.assertEqual(result['status'], 'complete')
            app = create_app(jobs, transport_token='synthetic-http-renderer-test-token-only')
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app),
                                         base_url='http://127.0.0.1:8942') as client:
                combined = await client.get('/')
                self.assertEqual(combined.status_code, 200)
                self.assertNotIn('refresh', combined.headers)
                self.assertIn('Mantle conversation', combined.text)
                self.assertIn('Validated source cards', combined.text)
                response = await client.get('/cards')
                self.assertEqual(response.status_code, 200)
                self.assertIn("default-src 'none'", response.headers['content-security-policy'])
                for heading in ('Flight status', 'Arrival weather', 'Arrival timeline', 'REPLAY'):
                    self.assertIn(heading, response.text)
                self.assertIn('<svg', response.text)
                self.assertNotIn('<script', response.text)
                self.assertNotIn(started['job_id'], response.text)
                refused = await client.get('/cards', params={'briefing_id': started['job_id']})
                self.assertEqual(refused.status_code, 400)
                self.assertNotIn(started['job_id'], refused.text)
        finally:
            await jobs.close()
