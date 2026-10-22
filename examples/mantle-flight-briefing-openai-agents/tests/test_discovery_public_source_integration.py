"""Released Core finder -> actual MCP selection -> natural meeting -> four cards.

Offline provider controls only. Run with the final locked project interpreter.
No live network/model, no private key, no replacement Core implementation.
"""
import asyncio
import unittest
from datetime import datetime, timezone, timedelta
from importlib.metadata import version
import json
from pathlib import Path
import sys
import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from zeo_core.integrations.briefing_sources import PublicBriefingSources, PublicSourceHTTP
from briefing.public_sources import PublicSourcesRunner
from briefing.jobs import Jobs
from briefing.mcp_app import create_app

async def main():
    assert hasattr(PublicBriefingSources, 'find_flights'), 'Final registry finder release is required; no substitute'
    now = datetime(2026, 10, 22, 12, tzinfo=timezone.utc)
    requests = []
    tick = [0.0]
    def aircraft(callsign):
        return {'flight': callsign, 'lat': 40.8, 'lon': -73.8, 'gs': 350,
                'seen_pos': 5, 'alt_baro': 25000, 'registered_owner': 'PRIVATE CANARY'}
    def handler(request):
        requests.append(request)
        if request.url.host == 'api.adsb.lol':
            if request.method == 'GET':
                rows = [aircraft('UNMATCHED') for _ in range(300)] if '/point/' in request.url.path else []
                if rows:
                    rows[249] = aircraft('DLH400')
                    rows[250] = aircraft('BAW117')
                else:
                    rows = [aircraft('DLH400')]
                return httpx.Response(200, json={'now': now.timestamp(), 'ac': rows})
            return httpx.Response(200, json=[{'callsign': 'DLH400', 'plausible': True,
                '_airports': [{'icao': 'EDDF', 'lat': 50.03, 'lon': 8.57},
                              {'icao': 'KJFK', 'lat': 40.64, 'lon': -73.78}]}])
        if request.url.host == 'api.met.no':
            return httpx.Response(200, json={'properties': {'meta': {'updated_at': now.isoformat()},
                'timeseries': [{'time': (now + timedelta(hours=i)).isoformat(), 'data': {
                    'instant': {'details': {'air_temperature': 15+i}},
                    'next_1_hours': {'details': {'precipitation_amount': .1,
                                                'probability_of_precipitation': 25}}}} for i in range(4)]}})
        assert request.url.host == 'data-api.ecb.europa.eu'
        return httpx.Response(200, text='FREQ,CURRENCY,CURRENCY_DENOM,EXR_TYPE,EXR_SUFFIX,TIME_PERIOD,OBS_VALUE\n'
            'D,USD,EUR,SP00,A,2026-10-20,1.1\nD,USD,EUR,SP00,A,2026-10-21,1.2\n'
            'D,GBP,EUR,SP00,A,2026-10-20,0.8\nD,GBP,EUR,SP00,A,2026-10-21,0.9\n')
    def sleep(seconds):
        tick[0] += seconds
    source = PublicBriefingSources(PublicSourceHTTP(transport=httpx.MockTransport(handler),
        clock=lambda: now, monotonic=lambda: tick[0], sleep=sleep), clock=lambda: now)
    runner = PublicSourcesRunner(source, clock=lambda: now)
    jobs = Jobs(runner, ownership_mode='capability')
    app = create_app(jobs, transport_token='synthetic-source-discovery-control-only')
    try:
        async with app._app.router.lifespan_context(app._app):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url='http://127.0.0.1:8942',
                    headers={'accept':'application/json, text/event-stream',
                             'authorization':'Bearer synthetic-source-discovery-control-only'}) as client:
                count = 0
                async def rpc(method, params):
                    nonlocal count
                    count += 1
                    result = await client.post('/mcp', json={'jsonrpc':'2.0','id':count,'method':method,'params':params})
                    assert result.status_code == 200
                    return result.json()['result']
                await rpc('initialize', {'protocolVersion':'2025-06-18','capabilities':{},'clientInfo':{'name':'control','version':'1'}})
                async def call(name, arguments):
                    answer = await rpc('tools/call', {'name':name,'arguments':arguments})
                    assert not answer.get('isError'), 'MCP control failed'
                    return answer['structuredContent']
                search = await call('find_flights', {'destination':'New York'})
                assert [r['callsign'] for r in search['candidates']] == ['BAW117','DLH400']
                assert search['partial'] is False
                page = (await client.get('/cards')).text
                assert jobs.display_place() is None
                assert 'Lufthansa 400' in page and 'CC0-1.0' in page
                assert search['discovery_id'] not in page and 'PRIVATE CANARY' not in page
                started = await call('briefing', {'action':'start','request':'the second one',
                    'discovery_id':search['discovery_id'],'choice':2})
                key = started['briefing_id']
                await jobs._jobs[key].task
                waiting = await call('briefing', {'action':'get','briefing_id':key})
                assert waiting['status'] == 'needs_input'
                assert waiting['needs_input']['field'] == 'meeting_time'
                await call('briefing', {'action':'revise','briefing_id':key,'change':'the 6 pm meeting tomorrow'})
                await jobs._jobs[key].task
                final = await call('briefing', {'action':'get','briefing_id':key})
                assert final['status'] == 'complete', final.get('reason', final['status'])
                assert len(final['cards']) == 4
                assert all(not c['data_ref']['replay'] and c['data_ref']['error'] is None for c in final['cards'])
                inputs = jobs._jobs[key].inputs
                assert inputs['callsign'] == 'DLH400' and inputs['destination'] == 'KJFK'
                assert inputs['meeting_time'].endswith('18:00:00-04:00')
                assert inputs['transfer_minutes'] == 90 and inputs['transfer_assumed'] is True
                page = (await client.get('/cards')).text
                assert jobs.display_place().timezone == 'America/New_York'
                assert jobs.display_place().code == 'JFK'
                assert 'New York' in page and 'local time' in page
                assert 'forecast, issued' in page
                assert page.count('as of 08:00 at JFK') >= 2
                # Viewing later does not silently turn snapshot-relative time
                # into a fresh observation. The visible reference stays fixed.
                now += timedelta(hours=2)
                later_page = (await client.get('/cards')).text
                assert later_page == page
                assert 'as of 10:00 at JFK' not in later_page
                timeline = next(c for c in final['cards'] if c['event']['component'] == 'arrival_timeline')
                assert any(a['label'] == 'airport_city_planning_allowance' for a in timeline['data_ref']['assumptions'])
                assert 'ASSUMPTION' in page and 'not live traffic' in page
                assert key not in page and 'PRIVATE CANARY' not in page
                assert len([r for r in requests if '/point/' in r.url.path]) == 1
                assert all(r.url.host in {'api.adsb.lol','api.met.no','data-api.ecb.europa.eu'} for r in requests)
                print(json.dumps({'result':'ACCEPT_OFFLINE_RELEASED_FINDER_INTEGRATION','core':version('zeocore'),
                    'candidates':2,'selected':'second','cards':4,'providerRequests':len(requests),
                    'scope':'actual released Core + MCP + source callbacks, injected provider payloads; no live/model/browser acceptance'}))
    finally:
        await jobs.close()
        runner.close()

class ReleasedFinderIntegration(unittest.IsolatedAsyncioTestCase):
    async def test_released_finder_to_selected_journey_and_four_cards(self):
        await main()


if __name__ == '__main__':
    unittest.main()
