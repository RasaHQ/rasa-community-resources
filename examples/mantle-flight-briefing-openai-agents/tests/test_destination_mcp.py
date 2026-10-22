"""Real MCP protocol and Core reader code; synthetic public-source HTTP only."""
import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from zeo_core.integrations.briefing_sources import PublicBriefingSources, PublicSourceHTTP
from briefing.jobs import Jobs
from briefing.mcp_app import create_app
from briefing.public_sources import PublicSourcesRunner
from test_mcp_display_lifetime import result_value

NOW = datetime(2026, 10, 22, 1, tzinfo=timezone.utc)


def fixture_sources():
    requests = []
    tick = [0.0]
    def handler(request):
        requests.append(request)
        if request.url.host == 'api.adsb.lol':
            if request.method == 'POST':
                return httpx.Response(201)  # Recorded status/empty shape; synthetic position.
            return httpx.Response(200, json={'now': NOW.timestamp() * 1000, 'ac': [{
                'flight': 'TEST123', 'lat': 50.0, 'lon': 0.0, 'gs': 400.0,
                'seen_pos': 5, 'alt_baro': 30000}]})
        if request.url.host == 'api.met.no':
            return httpx.Response(200, json={'properties': {'meta': {'updated_at': NOW.isoformat()},
                'timeseries': [{'time': (NOW + timedelta(hours=i)).isoformat(), 'data': {
                    'instant': {'details': {'air_temperature': 15 + i}},
                    'next_1_hours': {'details': {'precipitation_amount': .1,
                                               'probability_of_precipitation': 25}}}}
                               for i in range(4)]}})
        assert request.url.host == 'data-api.ecb.europa.eu'
        return httpx.Response(200, text='FREQ,CURRENCY,CURRENCY_DENOM,EXR_TYPE,EXR_SUFFIX,TIME_PERIOD,OBS_VALUE\n'
            'D,USD,EUR,SP00,A,2026-10-20,1.1\nD,USD,EUR,SP00,A,2026-10-21,1.2\n'
            'D,GBP,EUR,SP00,A,2026-10-20,0.8\nD,GBP,EUR,SP00,A,2026-10-21,0.9\n')
    def sleep(seconds):
        tick[0] += seconds
    return PublicBriefingSources(PublicSourceHTTP(transport=httpx.MockTransport(handler),
        clock=lambda: NOW, monotonic=lambda: tick[0], sleep=sleep), clock=lambda: NOW), requests


class StatedDestinationMCP(unittest.IsolatedAsyncioTestCase):
    runner_type = PublicSourcesRunner

    async def test_empty_route_explicit_destination_reaches_four_cards_via_actual_mcp(self):
        sources, requests = fixture_sources()
        runner = self.runner_type(sources)
        jobs = Jobs(runner, ownership_mode='capability')
        app = create_app(jobs, transport_token='synthetic-destination-protocol-control')
        try:
            async with app._app.router.lifespan_context(app._app):
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app),
                        base_url='http://127.0.0.1:8942',
                        headers={'Authorization': 'Bearer synthetic-destination-protocol-control'}) as http:
                    async with streamable_http_client('http://127.0.0.1:8942/mcp', http_client=http) as (read, write, _):
                        async with ClientSession(read, write) as session:
                            await session.initialize()
                            start = result_value(await session.call_tool('briefing', {'action': 'start',
                                'request': 'callsign=TEST123 destination=LHR meeting=2026-10-22T06:00:00Z transfer=45'}))
                            for _ in range(60):
                                state = result_value(await session.call_tool('briefing',
                                    {'action': 'get', 'briefing_id': start['briefing_id']}))
                                if state['status'] not in ('started', 'running'):
                                    break
                                await asyncio.sleep(.01)
                            self.assertEqual(state['status'], 'complete')
                            self.assertEqual(len(state['cards']), 4)
                            self.assertTrue(all(not card['data_ref']['replay'] for card in state['cards']))
                            page = await http.get('/cards')
                            for text in ('Route not provided by the source', 'destination stated by traveller',
                                         'EGLL', 'ASSUMPTION', 'COMPUTED', '30000 ft', '400 kt',
                                         'Arrival weather', 'Arrival timeline', 'Market watchlist'):
                                self.assertIn(text, page.text)
                            self.assertNotIn(start['briefing_id'], page.text)
                            self.assertEqual({r.url.host for r in requests},
                                             {'api.adsb.lol', 'api.met.no', 'data-api.ecb.europa.eu'})
        finally:
            await jobs.close()
            runner.close()
