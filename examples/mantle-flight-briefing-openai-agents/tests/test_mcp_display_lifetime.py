"""Actual stateless MCP requests share background jobs and the HTTP board.

All source values are offline unavailable controls. Protocol/request shutdown
must not own the application-wide job lifetime; no provider or Inspector runs.
"""
import asyncio
import json
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from zeo_core.contracts.ui.widgets import DataRef, DataError
from briefing.jobs import Jobs
from briefing.mcp_app import create_app
from briefing.public_sources import PublicSourcesRunner


class NoNetworkSources:
    def read_briefing(self, *args, **kwargs):
        return {component: DataRef(id=component, source='Offline unavailable source control',
            fetched_at='2026-10-22T01:00:00Z', as_of=None, replay=False, payload={},
            error=DataError(reason='Public source unavailable')) for component in (
                'flight_status', 'weather_hourly', 'arrival_timeline', 'market_watchlist')}
    def close(self):
        pass


def result_value(result):
    return result.structuredContent or json.loads(result.content[0].text)


class MCPDisplayLifetime(unittest.IsolatedAsyncioTestCase):
    async def test_jobs_span_stateless_requests_and_protocol_close_until_app_shutdown(self):
        release = asyncio.Event()
        source_runner = PublicSourcesRunner(NoNetworkSources())
        async def runner(work):
            await release.wait()
            return await source_runner(work)
        jobs = Jobs(runner, ownership_mode='capability')
        app = create_app(jobs, transport_token='synthetic-lifetime-control-token-only')
        async with app._app.router.lifespan_context(app._app):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app),
                    base_url='http://127.0.0.1:8942',
                    headers={'Authorization': 'Bearer synthetic-lifetime-control-token-only'}) as http:
                async with streamable_http_client('http://127.0.0.1:8942/mcp', http_client=http) as (read, write, _):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        started = result_value(await session.call_tool('briefing', {
                            'action': 'start',
                            'request': 'callsign=TEST123 destination=EDDF meeting=2026-10-22T06:00:00Z transfer=45'}))
                        capability = started['briefing_id']
                        for _ in range(2):
                            state = result_value(await session.call_tool('briefing',
                                {'action': 'get', 'briefing_id': capability}))
                            self.assertIn(state['status'], ('started', 'running'))
                        release.set()
                        for _ in range(30):
                            state = result_value(await session.call_tool('briefing',
                                {'action': 'get', 'briefing_id': capability}))
                            if state['status'] not in ('started', 'running'):
                                break
                            await asyncio.sleep(.01)
                        combined = await http.get('/')
                        page = await http.get('/cards')
                        self.assertEqual(combined.status_code, 200)
                        self.assertIn('Mantle conversation', combined.text)
                        self.assertIn('Validated source cards', combined.text)
                        self.assertEqual(page.status_code, 200)
                        for heading in ('Flight status', 'Arrival weather', 'Arrival timeline', 'Market watchlist'):
                            self.assertIn(heading, page.text)
                        self.assertNotIn('no cards yet', page.text.lower())
                        self.assertNotIn(capability, page.text)
                        self.assertEqual(state['status'], 'incomplete')
                        self.assertEqual(len(state['cards']), 4)
                # Ending the MCP protocol connection cannot clear the display.
                page = await http.get('/cards')
                self.assertIn('Market watchlist', page.text)
                self.assertEqual(len(jobs.display_snapshot()), 4)
        self.assertFalse(jobs.display_snapshot())
        source_runner.close()
