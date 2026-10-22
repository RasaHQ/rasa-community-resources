"""Released source adapters through Jobs, Core callbacks and the real HTTP app.

All provider responses below are synthetic offline controls. No provider,
model, voice or licensed Inspector call is made by this test.
"""
import asyncio
from datetime import datetime, timezone, timedelta
from importlib.metadata import version
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import httpx
from zeo_core.integrations.briefing_sources import PublicBriefingSources, PublicSourceHTTP
from briefing.public_sources import PublicSourcesRunner
from briefing.jobs import Jobs, Owner
from briefing.mcp_app import create_app

NOW = datetime(2026, 10, 22, 1, tzinfo=timezone.utc)


class ReleasedPublicSourceHTTP(unittest.IsolatedAsyncioTestCase):
    async def test_four_injected_source_cards_reach_combined_page_and_preserve_provenance(self):
        self.assertEqual(version('zeocore'), '0.35.0')
        requests = []
        tick = [0.0]
        def handler(request):
            requests.append(request)
            if request.url.host == 'api.adsb.lol':
                if request.method == 'GET':
                    return httpx.Response(200, json={'now': NOW.timestamp() * 1000, 'ac': [{
                        'flight': 'TEST123', 'lat': 50.0, 'lon': 0.0, 'gs': 400.0,
                        'seen_pos': 5, 'alt_baro': 30000, 'passenger': 'NEVER DISPLAY THIS'}]})
                return httpx.Response(200, json=[{'callsign': 'TEST123', 'plausible': True,
                    '_airports': [{'icao': 'KJFK', 'lat': 40.6, 'lon': -73.7},
                                  {'icao': 'EGLL', 'lat': 51.4775, 'lon': -0.4614}]}])
            if request.url.host == 'api.met.no':
                return httpx.Response(200, json={'properties': {'meta': {'updated_at': NOW.isoformat()},
                    'timeseries': [{'time': (NOW + timedelta(hours=i)).isoformat(), 'data': {
                        'instant': {'details': {'air_temperature': 15 + i}},
                        'next_1_hours': {'details': {'precipitation_amount': .1,
                                                     'probability_of_precipitation': 25}}}}
                                   for i in range(4)]}})
            self.assertEqual(request.url.host, 'data-api.ecb.europa.eu')
            return httpx.Response(200, text='FREQ,CURRENCY,CURRENCY_DENOM,EXR_TYPE,EXR_SUFFIX,TIME_PERIOD,OBS_VALUE\n'
                'D,USD,EUR,SP00,A,2026-10-20,1.1\nD,USD,EUR,SP00,A,2026-10-21,1.2\n'
                'D,GBP,EUR,SP00,A,2026-10-20,0.8\nD,GBP,EUR,SP00,A,2026-10-21,0.9\n')
        def sleep(seconds):
            tick[0] += seconds
        sources = PublicBriefingSources(PublicSourceHTTP(transport=httpx.MockTransport(handler),
            clock=lambda: NOW, monotonic=lambda: tick[0], sleep=sleep), clock=lambda: NOW)
        runner = PublicSourcesRunner(sources)
        jobs = Jobs(runner, replacement_plan=runner.replacement_plan, ownership_mode='capability')
        owner = Owner('mantle', 'capability-possession')
        started = await jobs.briefing(owner, action='start',
            request='callsign=TEST123 meeting=2026-10-22T06:00:00Z transfer=45')
        try:
            for _ in range(200):
                state = await jobs.briefing(owner, action='get', job_id=started['job_id'])
                if state['status'] not in ('started', 'running'):
                    break
                await asyncio.sleep(.01)
            self.assertEqual(state['status'], 'complete')
            self.assertEqual(len(state['cards']), 4)
            self.assertTrue(all(not card['data_ref']['replay'] for card in state['cards']))
            app = create_app(jobs, transport_token='synthetic-offline-class-http-token-only')
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app),
                                         base_url='http://127.0.0.1:8942') as client:
                page = await client.get('/cards')
                self.assertEqual(page.status_code, 200)
                for text in ('Flight status', 'Arrival weather', 'Arrival timeline', 'Market watchlist',
                             'ODbL 1.0', 'CC BY 4.0', 'daily reference rate', '2026-10-21',
                             'COMPUTED from two reference days', 'not an airline time'):
                    self.assertIn(text, page.text)
                for forbidden in ('[withheld]', 'NEVER DISPLAY THIS', started['job_id'], '<script'):
                    self.assertNotIn(forbidden, page.text)
                combined = await client.get('/')
                self.assertEqual(combined.status_code, 200)
                self.assertIn('Mantle conversation', combined.text)
                self.assertNotIn('refresh', combined.headers)
            self.assertEqual({request.url.host for request in requests},
                             {'api.adsb.lol', 'api.met.no', 'data-api.ecb.europa.eu'})
            self.assertTrue(all('RasaCommunityFlightBriefing' in request.headers['User-Agent']
                                for request in requests))
        finally:
            await jobs.close()
            runner.close()
